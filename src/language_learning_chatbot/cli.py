"""Run a sentence check from a local terminal."""

import argparse
import os
import sys
from collections.abc import Sequence
from contextlib import AbstractContextManager

from .application import (
    CheckSentence,
    CheckSentenceRequest,
    GenerationFailure,
    SentenceEvaluator,
)
from .infrastructure.ollama_sentence_evaluator import OllamaSentenceEvaluator
from .infrastructure.openai_sentence_evaluator import OpenAISentenceEvaluator
from .infrastructure.sentence_evaluation import SentenceClarificationNeeded
from .presentation import render_sentence_feedback


def _evaluator_from_environment() -> AbstractContextManager[SentenceEvaluator]:
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider == "openai":
        return OpenAISentenceEvaluator.from_environment()
    if provider == "ollama":
        return OllamaSentenceEvaluator.from_environment()
    raise ValueError("Set LLM_PROVIDER to openai or ollama.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a Japanese sentence with a language model.")
    parser.add_argument("draft", help="Japanese draft to check")
    parser.add_argument("--context", help="Intended meaning, audience, or tone")
    args = parser.parse_args(argv)

    request = CheckSentenceRequest(draft=args.draft, context=args.context)
    try:
        with _evaluator_from_environment() as evaluator:
            feedback = CheckSentence(evaluator).execute(request)
    except SentenceClarificationNeeded as clarification:
        print(clarification.question)
        return 3
    except GenerationFailure as failure:
        print(failure, file=sys.stderr)
        return 1
    except ValueError as invalid_input:
        parser.error(str(invalid_input))

    print(render_sentence_feedback(feedback))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
