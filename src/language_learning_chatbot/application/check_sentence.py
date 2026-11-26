"""Check a draft in the requested language and return validated feedback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, TypeGuard


class SentenceFeedbackKind(str, Enum):
    """The three outcomes supported by the sentence-checking use case."""

    CORRECTION = "correction"
    SUGGESTION = "suggestion"
    ALREADY_NATURAL = "already_natural"


@dataclass(frozen=True, slots=True)
class CheckSentenceRequest:
    """A draft and context as typed by the user, plus two language choices.

    ``target_language`` is the language being learned and checked.
    ``tutorial_language`` is the language used for explanations. Both accept
    open language tags, such as ``ja``, ``fr``, or ``zh-TW``.
    """

    draft: str
    context: str | None = None
    tutorial_language: str = "zh-TW"
    target_language: str = "ja"


@dataclass(frozen=True, slots=True)
class SentenceEvaluation:
    """Structured content returned by a sentence evaluator.

    Corrections and suggestions require a ``sentence`` in the target language
    and an ``explanation`` in the tutorial language. A suggestion also
    requires an ``original_validity_note`` in the tutorial language.
    All content fields must be absent when the draft is already natural.
    """

    kind: SentenceFeedbackKind
    sentence: str | None = None
    explanation: str | None = None
    original_validity_note: str | None = None


class SentenceEvaluator(Protocol):
    """Application-owned port implemented later by an AI adapter."""

    def evaluate(self, request: CheckSentenceRequest) -> SentenceEvaluation | None:
        """Check the draft in the target language using the tutorial language for notes."""


@dataclass(frozen=True, slots=True)
class SentenceFeedback:
    """Validated output of ``CheckSentence``."""

    kind: SentenceFeedbackKind
    target_language: str
    tutorial_language: str
    sentence: str | None = None
    explanation: str | None = None
    original_validity_note: str | None = None


class GenerationFailure(RuntimeError):
    """The evaluator did not produce a complete, valid result."""


class CheckSentence:
    """Validate input, call the evaluator, and enforce the output contract."""

    def __init__(self, evaluator: SentenceEvaluator) -> None:
        self._evaluator = evaluator

    def execute(self, request: CheckSentenceRequest) -> SentenceFeedback:
        self._validate_request(request)
        evaluation = self._evaluator.evaluate(request)
        return self._validated_feedback(evaluation, request)

    @staticmethod
    def _validate_request(request: CheckSentenceRequest) -> None:
        if not isinstance(request, CheckSentenceRequest):
            raise TypeError("request must be a CheckSentenceRequest")
        if not isinstance(request.draft, str) or not request.draft.strip():
            raise ValueError("draft must be a non-empty string")
        if request.context is not None and not isinstance(request.context, str):
            raise ValueError("context must be a string or None")
        if not _is_non_empty_text(request.target_language):
            raise ValueError("target_language must be a non-empty language tag")
        if not _is_non_empty_text(request.tutorial_language):
            raise ValueError("tutorial_language must be a non-empty language tag")

    @staticmethod
    def _validated_feedback(
        evaluation: object, request: CheckSentenceRequest
    ) -> SentenceFeedback:
        if not isinstance(evaluation, SentenceEvaluation):
            raise GenerationFailure("Sentence evaluation was missing or malformed")

        if not isinstance(evaluation.kind, SentenceFeedbackKind):
            raise GenerationFailure("Sentence evaluation was missing or malformed")

        if evaluation.kind is SentenceFeedbackKind.ALREADY_NATURAL:
            if (
                evaluation.sentence is not None
                or evaluation.explanation is not None
                or evaluation.original_validity_note is not None
            ):
                raise GenerationFailure("Sentence evaluation was missing or malformed")
            return SentenceFeedback(
                kind=evaluation.kind,
                target_language=request.target_language,
                tutorial_language=request.tutorial_language,
            )

        if not _is_non_empty_text(evaluation.sentence) or not _is_non_empty_text(
            evaluation.explanation
        ):
            raise GenerationFailure("Sentence evaluation was missing or malformed")

        if evaluation.kind is SentenceFeedbackKind.SUGGESTION:
            if not _is_non_empty_text(evaluation.original_validity_note):
                raise GenerationFailure("Sentence evaluation was missing or malformed")
        elif evaluation.original_validity_note is not None:
            raise GenerationFailure("Sentence evaluation was missing or malformed")

        return SentenceFeedback(
            kind=evaluation.kind,
            target_language=request.target_language,
            tutorial_language=request.tutorial_language,
            sentence=evaluation.sentence.strip(),
            explanation=evaluation.explanation.strip(),
            original_validity_note=(
                evaluation.original_validity_note.strip()
                if evaluation.original_validity_note is not None
                else None
            ),
        )


def _is_non_empty_text(value: object) -> TypeGuard[str]:
    return isinstance(value, str) and bool(value.strip())

