"""Evaluate sentence drafts through a local Ollama server."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager

import httpx

from ..application import CheckSentenceRequest, GenerationFailure, SentenceEvaluation
from .sentence_evaluation import (
    INSTRUCTIONS,
    MAX_OUTPUT_TOKENS,
    SENTENCE_EVALUATION_SCHEMA,
    parse_evaluation,
    serialize_request,
)


_DEFAULT_BASE_URL = "http://127.0.0.1:11434"
_TIMEOUT_SECONDS = 90.0
_OLLAMA_INSTRUCTIONS = (
    INSTRUCTIONS
    + "\nRespond with one JSON object matching this schema:\n"
    + json.dumps(SENTENCE_EVALUATION_SCHEMA, separators=(",", ":"))
)


class OllamaSentenceEvaluator:
    """Map Ollama chat output onto the application evaluator contract."""

    def __init__(self, client: httpx.Client, model: str) -> None:
        self._client = client
        self._model = model

    @classmethod
    @contextmanager
    def from_environment(cls) -> Iterator[OllamaSentenceEvaluator]:
        model = os.getenv("OLLAMA_MODEL", "").strip()
        if not model:
            raise ValueError("Set OLLAMA_MODEL to a model installed in Ollama.")

        address = os.getenv("OLLAMA_BASE_URL", "").strip() or _DEFAULT_BASE_URL
        try:
            base_url = httpx.URL(address)
        except httpx.InvalidURL:
            raise ValueError("Set OLLAMA_BASE_URL to a valid HTTP or HTTPS URL.") from None
        if base_url.scheme not in {"http", "https"} or not base_url.host:
            raise ValueError("Set OLLAMA_BASE_URL to a valid HTTP or HTTPS URL.")

        with httpx.Client(
            base_url=base_url,
            timeout=_TIMEOUT_SECONDS,
            trust_env=False,
        ) as client:
            yield cls(client, model)

    def evaluate(self, request: CheckSentenceRequest) -> SentenceEvaluation:
        try:
            response = self._client.post(
                "api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _OLLAMA_INSTRUCTIONS},
                        {"role": "user", "content": serialize_request(request)},
                    ],
                    "stream": False,
                    "format": SENTENCE_EVALUATION_SCHEMA,
                    "options": {"temperature": 0, "num_predict": MAX_OUTPUT_TOKENS},
                },
            )
            if response.status_code == 404:
                raise GenerationFailure(
                    "Ollama could not find the model or chat endpoint. "
                    "Check OLLAMA_MODEL and OLLAMA_BASE_URL."
                )
            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException:
            raise GenerationFailure("Ollama timed out while checking the sentence.") from None
        except httpx.ConnectError:
            raise GenerationFailure(
                "Could not connect to Ollama. Start Ollama and check OLLAMA_BASE_URL."
            ) from None
        except httpx.HTTPError:
            raise GenerationFailure("Ollama could not complete the request.") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GenerationFailure("Ollama returned an invalid response.") from None

        return parse_evaluation(_response_text(payload), "Ollama")


def _response_text(payload: object) -> str:
    if not isinstance(payload, dict) or not isinstance(payload.get("done"), bool):
        raise GenerationFailure("Ollama returned an invalid response.")
    if not payload["done"] or payload.get("done_reason") not in (None, "stop"):
        raise GenerationFailure("Ollama returned an incomplete response.")

    message = payload.get("message")
    if isinstance(message, dict) and message.get("role") == "assistant":
        content = message.get("content")
        if isinstance(content, str):
            return content
    raise GenerationFailure("Ollama returned an invalid response.")
