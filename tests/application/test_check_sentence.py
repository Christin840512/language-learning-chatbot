from __future__ import annotations

import unittest
from typing import cast

from src.language_learning_chatbot.application import (
    CheckSentence,
    CheckSentenceRequest,
    GenerationFailure,
    SentenceEvaluation,
    SentenceFeedbackKind,
)
from src.language_learning_chatbot.presentation import render_sentence_feedback


class FakeSentenceEvaluator:
    def __init__(self, result: object) -> None:
        self.result = result
        self.requests: list[CheckSentenceRequest] = []

    def evaluate(self, request: CheckSentenceRequest) -> SentenceEvaluation | None:
        self.requests.append(request)
        return cast(SentenceEvaluation | None, self.result)


class CheckSentenceTests(unittest.TestCase):
    def test_correction_uses_japanese_and_traditional_chinese_by_default(self) -> None:
        evaluator = FakeSentenceEvaluator(
            SentenceEvaluation(
                kind=SentenceFeedbackKind.CORRECTION,
                sentence="買ってみます",
                explanation="「試著做」要使用動詞て形加上「みる」。",
            )
        )
        use_case = CheckSentence(evaluator)
        request = CheckSentenceRequest(
            draft="買い見ます",
            context="想表達『我會試著買看看』",
        )

        feedback = use_case.execute(request)

        self.assertEqual(evaluator.requests, [request])
        self.assertEqual(feedback.kind, SentenceFeedbackKind.CORRECTION)
        self.assertEqual(feedback.target_language, "ja")
        self.assertEqual(feedback.tutorial_language, "zh-TW")
        self.assertEqual(feedback.sentence, "買ってみます")
        self.assertEqual(
            render_sentence_feedback(feedback),
            "買ってみます\n\n「試著做」要使用動詞て形加上「みる」。",
        )

    def test_suggestion_explicitly_says_the_original_is_valid(self) -> None:
        evaluator = FakeSentenceEvaluator(
            SentenceEvaluation(
                kind=SentenceFeedbackKind.SUGGESTION,
                sentence="うん、行こう",
                explanation="和朋友聊天時，「うん」比「はい」更符合輕鬆的語氣。",
                original_validity_note="原句是正確的。",
            )
        )
        use_case = CheckSentence(evaluator)

        feedback = use_case.execute(CheckSentenceRequest(draft="はい、行こう"))
        rendered = render_sentence_feedback(feedback)

        self.assertEqual(feedback.kind, SentenceFeedbackKind.SUGGESTION)
        self.assertIn("原句是正確的。", rendered)
        self.assertIn("うん、行こう", rendered)
        self.assertIn("和朋友聊天時", rendered)

    def test_french_target_with_english_tutorial(self) -> None:
        evaluator = FakeSentenceEvaluator(
            SentenceEvaluation(
                kind=SentenceFeedbackKind.SUGGESTION,
                sentence="Salut, ça va ?",
                explanation="With a close friend, « salut » is more casual.",
                original_validity_note="The original sentence is valid.",
            )
        )
        use_case = CheckSentence(evaluator)
        request = CheckSentenceRequest(
            draft="  Bonjour, ça va ?  ",
            context="  跟朋友聊天 (casual)  ",
            target_language="fr",
            tutorial_language="en",
        )

        feedback = use_case.execute(request)
        rendered = render_sentence_feedback(feedback)

        self.assertEqual(evaluator.requests, [request])
        self.assertEqual(feedback.target_language, "fr")
        self.assertEqual(feedback.tutorial_language, "en")
        self.assertEqual(
            rendered,
            "The original sentence is valid.\n\n"
            "Salut, ça va ?\n\n"
            "With a close friend, « salut » is more casual.",
        )

    def test_already_natural_renders_as_exact_success_message(self) -> None:
        evaluator = FakeSentenceEvaluator(
            SentenceEvaluation(kind=SentenceFeedbackKind.ALREADY_NATURAL)
        )
        use_case = CheckSentence(evaluator)

        feedback = use_case.execute(
            CheckSentenceRequest(draft="今度、ぜひ食べてみるよ")
        )

        self.assertEqual(feedback.kind, SentenceFeedbackKind.ALREADY_NATURAL)
        self.assertEqual(render_sentence_feedback(feedback), "Well done!")

    def test_missing_or_malformed_evaluation_is_a_generation_failure(self) -> None:
        invalid_results = (
            None,
            {"kind": "correction"},
            SentenceEvaluation(
                kind=SentenceFeedbackKind.CORRECTION,
                sentence="買ってみます",
            ),
            SentenceEvaluation(
                kind=cast(SentenceFeedbackKind, "correction"),
                sentence="買ってみます",
                explanation="說明",
            ),
            SentenceEvaluation(
                kind=SentenceFeedbackKind.SUGGESTION,
                sentence="うん、行こう",
                explanation="原句可用，但這個說法更自然。",
            ),
            SentenceEvaluation(
                kind=SentenceFeedbackKind.ALREADY_NATURAL,
                sentence="不應存在的內容",
            ),
        )

        for invalid_result in invalid_results:
            with self.subTest(invalid_result=invalid_result):
                use_case = CheckSentence(FakeSentenceEvaluator(invalid_result))

                with self.assertRaisesRegex(
                    GenerationFailure, "missing or malformed"
                ):
                    use_case.execute(CheckSentenceRequest(draft="買い見ます"))

    def test_blank_language_choice_fails_before_evaluation(self) -> None:
        evaluator = FakeSentenceEvaluator(None)
        use_case = CheckSentence(evaluator)
        cases = (
            (
                "target_language",
                CheckSentenceRequest(draft="Salut", target_language=" "),
            ),
            (
                "tutorial_language",
                CheckSentenceRequest(draft="Salut", tutorial_language=""),
            ),
        )

        for field, request in cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    use_case.execute(request)

        self.assertEqual(evaluator.requests, [])


if __name__ == "__main__":
    unittest.main()
