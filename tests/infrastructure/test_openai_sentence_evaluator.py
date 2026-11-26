import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from typing import Any
from unittest.mock import patch

import httpx
from openai import OpenAI

from src.language_learning_chatbot.application import (
    CheckSentence,
    CheckSentenceRequest,
    GenerationFailure,
)
from src.language_learning_chatbot.cli import main
from src.language_learning_chatbot.infrastructure import openai_sentence_evaluator
from src.language_learning_chatbot.infrastructure.openai_sentence_evaluator import (
    OpenAISentenceEvaluator,
)
from src.language_learning_chatbot.presentation import render_sentence_feedback


def _text_part(outcome: dict[str, object]) -> dict[str, object]:
    return {
        "type": "output_text",
        "text": json.dumps({"outcome": outcome}, ensure_ascii=False),
        "annotations": [],
    }


def _response(*parts: dict[str, object], status: str = "completed") -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "resp_test",
            "object": "response",
            "status": status,
            "created_at": 0,
            "model": "test-model",
            "parallel_tool_calls": False,
            "tool_choice": "auto",
            "tools": [],
            "output": [
                {
                    "id": "msg_test",
                    "type": "message",
                    "role": "assistant",
                    "status": status,
                    "content": parts,
                }
            ],
        },
    )


class OpenAISentenceEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.reply: httpx.Response | Exception = _response(
            _text_part({"kind": "already_natural"})
        )

    def _transport(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    def _check(self, request: CheckSentenceRequest) -> str:
        with self._local_client(api_key="test-key", max_retries=0) as client:
            evaluator = OpenAISentenceEvaluator(client, "test-model")
            return render_sentence_feedback(CheckSentence(evaluator).execute(request))

    def test_correction_sends_one_strict_request_with_draft_and_context(self) -> None:
        self.reply = _response(
            _text_part({
                "kind": "correction",
                "sentence": "買ってみます",
                "explanation": "「試著做」要用動詞て形加上「みる」。",
            })
        )

        result = self._check(CheckSentenceRequest(" 買い見ます ", " 想試著買 "))

        self.assertEqual(result, "買ってみます\n\n「試著做」要用動詞て形加上「みる」。")
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0].url.path, "/v1/responses")
        body = json.loads(self.requests[0].content)
        self.assertEqual(body["model"], "test-model")
        self.assertEqual(
            json.loads(body["input"]),
            {
                "draft": " 買い見ます ",
                "context": " 想試著買 ",
                "target_language": "ja",
                "tutorial_language": "zh-TW",
            },
        )
        self.assertIn("Traditional Chinese", body["instructions"])
        self.assertFalse(body["store"])
        self.assertEqual(body["max_output_tokens"], 1024)
        self.assertEqual(body["text"]["format"]["type"], "json_schema")
        self.assertTrue(body["text"]["format"]["strict"])

    def test_suggestion_includes_validity_note(self) -> None:
        self.reply = _response(
            _text_part({
                "kind": "suggestion",
                "sentence": "うん、行こう",
                "explanation": "「うん」更符合跟朋友聊天的語氣。",
                "original_validity_note": "原句是正確的。",
            })
        )

        result = self._check(CheckSentenceRequest("はい、行こう", "跟朋友聊天"))

        self.assertEqual(
            result, "原句是正確的。\n\nうん、行こう\n\n「うん」更符合跟朋友聊天的語氣。"
        )

    def test_natural_draft_renders_exact_message_and_preserves_language_choices(self) -> None:
        result = self._check(
            CheckSentenceRequest("Salut, ça va ?", tutorial_language="en", target_language="fr")
        )

        self.assertEqual(result, "Well done!")
        data = json.loads(json.loads(self.requests[0].content)["input"])
        self.assertIsNone(data["context"])
        self.assertEqual(data["target_language"], "fr")
        self.assertEqual(data["tutorial_language"], "en")

    def test_malformed_feedback_fails(self) -> None:
        cases = (
            {"kind": "unknown"},
            {"kind": "correction", "sentence": "買ってみます"},
            {"kind": "correction", "sentence": 42, "explanation": "說明"},
            {"kind": "suggestion", "sentence": "うん、行こう", "explanation": "說明"},
            {"kind": "correction", "sentence": "買ってみます", "explanation": "  "},
            {"kind": "correction", "sentence": "買ってみます", "explanation": "長" * 1001},
            {"kind": "already_natural", "explanation": "不應存在的內容"},
            {"kind": "clarification", "question": "　"},
        )
        for outcome in cases:
            with self.subTest(outcome=outcome):
                self.reply = _response(_text_part(outcome))
                with self.assertRaisesRegex(GenerationFailure, "invalid sentence feedback"):
                    self._check(CheckSentenceRequest("買い見ます"))

    def test_refusal_incomplete_and_invalid_payloads_are_distinct_failures(self) -> None:
        partial = {"type": "output_text", "text": '{"outcome":', "annotations": []}
        cases = (
            (_response({"type": "refusal", "refusal": "Raw provider text"}), "refused"),
            (_response(partial, status="incomplete"), "incomplete"),
            (_response(partial), "invalid sentence feedback"),
            (_response(), "exactly one"),
            (_response(partial, partial), "exactly one"),
            (
                httpx.Response(200, headers={"Content-Type": "application/json"}, text="{"),
                "invalid response",
            ),
            (httpx.Response(503, text="Raw provider text"), "could not complete"),
        )
        for reply, message in cases:
            with self.subTest(message=message):
                self.reply = reply
                with self.assertRaisesRegex(GenerationFailure, message) as error:
                    self._check(CheckSentenceRequest("買い見ます"))
                self.assertNotIn("Raw provider text", str(error.exception))

    def test_cli_asks_for_clarification_and_applies_transport_limits(self) -> None:
        question = "你是想說「去買」，還是「試著買」？"
        self.reply = _response(_text_part({"kind": "clarification", "question": question}))
        stdout = io.StringIO()
        stderr = io.StringIO()

        with (
            patch.dict(
                "os.environ",
                {
                    "LLM_PROVIDER": "openai",
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_MODEL": "test-model",
                },
            ),
            patch.object(openai_sentence_evaluator, "OpenAI", side_effect=self._local_client),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            self.assertEqual(main(["買い見ます"]), 3)
            self.reply = httpx.ReadTimeout("Raw provider text")
            self.assertEqual(main(["買い見ます"]), 1)
            self.reply = _response(_text_part({"kind": "already_natural"}))
            self.assertEqual(main(["今度、ぜひ食べてみるよ"]), 0)

        self.assertEqual(stdout.getvalue(), f"{question}\nWell done!\n")
        self.assertEqual(stderr.getvalue(), "OpenAI timed out while checking the sentence.\n")
        self.assertEqual(len(self.requests), 3)
        for request in self.requests:
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(request.extensions["timeout"]["read"], 15.0)
            self.assertEqual(json.loads(request.content)["model"], "test-model")

    def _local_client(self, **settings: Any) -> OpenAI:
        return OpenAI(
            **settings,
            base_url="https://openai.test/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(self._transport)),
        )
