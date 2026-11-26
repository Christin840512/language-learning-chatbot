"""Evaluate sentence drafts through the OpenAI Responses API."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager

from openai import APIError, APITimeoutError, OpenAI
from openai.types.responses import (
    Response,
    ResponseOutputMessage,
    ResponseOutputRefusal,
    ResponseOutputText,
    ResponseReasoningItem,
)

from ..application import CheckSentenceRequest, GenerationFailure, SentenceEvaluation
from .sentence_evaluation import (
    INSTRUCTIONS,
    MAX_OUTPUT_TOKENS,
    SENTENCE_EVALUATION_SCHEMA,
    SentenceClarificationNeeded as SentenceClarificationNeeded,
    parse_evaluation,
    serialize_request,
)


_TIMEOUT_SECONDS = 15.0


class OpenAISentenceEvaluator:
    """Map a provider response onto the application evaluator contract."""

    def __init__(self, client: OpenAI, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    @contextmanager
    def from_environment(cls) -> Iterator[OpenAISentenceEvaluator]:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        model = os.getenv("OPENAI_MODEL", "").strip()
        if not api_key or not model:
            raise ValueError("Set OPENAI_API_KEY and OPENAI_MODEL before running a check.")
        with OpenAI(api_key=api_key, timeout=_TIMEOUT_SECONDS, max_retries=0) as client:
            yield cls(client, model)

    def evaluate(self, request: CheckSentenceRequest) -> SentenceEvaluation:
        try:
            response = self._client.responses.create(
                model=self._model,
                instructions=INSTRUCTIONS,
                input=serialize_request(request),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "sentence_check_v1",
                        "strict": True,
                        "schema": SENTENCE_EVALUATION_SCHEMA,
                    },
                },
                max_output_tokens=MAX_OUTPUT_TOKENS,
                store=False,
            )
        except APITimeoutError:
            raise GenerationFailure(
                "OpenAI timed out while checking the sentence."
            ) from None
        except json.JSONDecodeError:
            raise GenerationFailure("OpenAI returned an invalid response.") from None
        except APIError:
            raise GenerationFailure("OpenAI could not complete the request.") from None

        return parse_evaluation(_response_text(response), "OpenAI")


def _response_text(response: Response) -> str:
    if not isinstance(response, Response):
        raise GenerationFailure("OpenAI returned an invalid response.")
    if response.status == "incomplete":
        raise GenerationFailure("OpenAI returned an incomplete response.")
    if response.status != "completed":
        raise GenerationFailure("OpenAI did not complete the sentence check.")

    output = getattr(response, "output", None)
    if not isinstance(output, list):
        raise GenerationFailure("OpenAI returned an invalid response.")
    messages = [item for item in output if not isinstance(item, ResponseReasoningItem)]
    if len(messages) != 1 or not isinstance(messages[0], ResponseOutputMessage):
        raise GenerationFailure("OpenAI did not return exactly one sentence-check result.")

    message = messages[0]
    status = getattr(message, "status", None)
    if status == "incomplete":
        raise GenerationFailure("OpenAI returned an incomplete response.")
    content = getattr(message, "content", None)
    if status != "completed" or not isinstance(content, list):
        raise GenerationFailure("OpenAI returned an invalid response.")
    if any(isinstance(part, ResponseOutputRefusal) for part in content):
        raise GenerationFailure("OpenAI refused to check the sentence.")
    if len(content) == 1 and isinstance(content[0], ResponseOutputText):
        text = getattr(content[0], "text", None)
        if isinstance(text, str):
            return text
    raise GenerationFailure("OpenAI did not return exactly one sentence-check result.")
