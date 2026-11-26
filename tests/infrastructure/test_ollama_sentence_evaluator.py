import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import httpx

from src.language_learning_chatbot.application import CheckSentenceRequest, GenerationFailure
from src.language_learning_chatbot.cli import main
from src.language_learning_chatbot.infrastructure.ollama_sentence_evaluator import (
    OllamaSentenceEvaluator,
)
from src.language_learning_chatbot.infrastructure.openai_sentence_evaluator import (
    OpenAISentenceEvaluator,
)


class OllamaSentenceEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[httpx.Request] = []
        self.reply: httpx.Response | httpx.HTTPError = httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps({
                        "outcome": {
                            "kind": "correction",
                            "sentence": "買ってみます",
                            "explanation": "「試著做」要用動詞て形加上「みる」。",
                        }
                    }),
                },
            },
        )

    def _transport(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if isinstance(self.reply, httpx.HTTPError):
            raise self.reply
        return self.reply

    def test_cli_selects_ollama_and_sends_a_structured_request_without_a_key(self) -> None:
        settings = {
            "LLM_PROVIDER": "ollama",
            "OLLAMA_MODEL": "local-model",
            "OLLAMA_BASE_URL": "http://127.0.0.1:11435",
        }
        stdout = io.StringIO()
        client_class = httpx.Client
        with (
            patch.dict("os.environ", settings, clear=True),
            patch.object(
                httpx,
                "Client",
                side_effect=lambda **config: client_class(
                    **config, transport=httpx.MockTransport(self._transport)
                ),
            ),
            patch.object(OpenAISentenceEvaluator, "from_environment") as openai,
            redirect_stdout(stdout),
        ):
            self.assertEqual(main([" 買い見ます ", "--context", " 想試著買 "]), 0)

        openai.assert_not_called()
        self.assertEqual(stdout.getvalue(), "買ってみます\n\n「試著做」要用動詞て形加上「みる」。\n")
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(str(request.url), "http://127.0.0.1:11435/api/chat")
        self.assertEqual(request.extensions["timeout"]["read"], 90.0)
        self.assertNotIn("Authorization", request.headers)
        body = json.loads(request.content)
        self.assertEqual(body["model"], "local-model")
        self.assertIs(body["stream"], False)
        self.assertIn("outcome", body["format"]["properties"])
        self.assertEqual(body["options"]["num_predict"], 1024)
        instructions, draft = body["messages"]
        self.assertEqual(instructions["role"], "system")
        self.assertEqual(draft["role"], "user")
        self.assertEqual(
            json.loads(draft["content"]),
            {
                "draft": " 買い見ます ",
                "context": " 想試著買 ",
                "target_language": "ja",
                "tutorial_language": "zh-TW",
            },
        )

    def test_ollama_reports_transport_and_invalid_output_failures(self) -> None:
        cases = (
            (httpx.ReadTimeout("raw timeout details"), "timed out"),
            (httpx.ConnectError("raw connection details"), "Could not connect"),
            (httpx.Response(404, text="raw server details"), "could not find"),
            (httpx.Response(500, text="raw server details"), "could not complete"),
            (httpx.Response(200, text="raw server details"), "invalid response"),
            (httpx.Response(200, json={"done": False}), "incomplete response"),
            (
                httpx.Response(200, json={"done": True, "done_reason": "length"}),
                "incomplete response",
            ),
            (httpx.Response(200, json={"done": True, "message": {}}), "invalid response"),
            (
                httpx.Response(
                    200,
                    json={"done": True, "message": {"role": "assistant", "content": "{}"}},
                ),
                "invalid sentence feedback",
            ),
        )
        with httpx.Client(
            base_url="http://127.0.0.1:11434",
            transport=httpx.MockTransport(self._transport),
        ) as client:
            evaluator = OllamaSentenceEvaluator(client, "local-model")
            for reply, message in cases:
                with self.subTest(message=message):
                    self.reply = reply
                    with self.assertRaisesRegex(GenerationFailure, message) as error:
                        evaluator.evaluate(CheckSentenceRequest("買い見ます"))
                    self.assertNotIn("raw ", str(error.exception))

        self.assertEqual(len(self.requests), len(cases))

    def test_cli_does_not_fall_back_to_openai_when_ollama_fails(self) -> None:
        self.reply = httpx.ConnectError("Connection refused")
        stderr = io.StringIO()
        client = httpx.Client(
            base_url="http://127.0.0.1:11434",
            transport=httpx.MockTransport(self._transport),
        )
        with (
            patch.dict(
                "os.environ",
                {"LLM_PROVIDER": "ollama", "OLLAMA_MODEL": "local-model"},
                clear=True,
            ),
            patch.object(httpx, "Client", return_value=client) as ollama_client,
            patch.object(OpenAISentenceEvaluator, "from_environment") as openai,
            redirect_stderr(stderr),
        ):
            self.assertEqual(main(["買い見ます"]), 1)

        openai.assert_not_called()
        self.assertEqual(str(ollama_client.call_args.kwargs["base_url"]), "http://127.0.0.1:11434")
        self.assertIn("Could not connect to Ollama", stderr.getvalue())

    def test_cli_rejects_invalid_configuration(self) -> None:
        cases = (
            ({"LLM_PROVIDER": "unknown"}, "Set LLM_PROVIDER"),
            ({"LLM_PROVIDER": "ollama"}, "Set OLLAMA_MODEL"),
            (
                {
                    "LLM_PROVIDER": "ollama",
                    "OLLAMA_MODEL": "local-model",
                    "OLLAMA_BASE_URL": "invalid",
                },
                "Set OLLAMA_BASE_URL",
            ),
        )
        for settings, message in cases:
            stderr = io.StringIO()
            with (
                self.subTest(settings=settings),
                patch.dict("os.environ", settings, clear=True),
                redirect_stderr(stderr),
                self.assertRaises(SystemExit) as error,
            ):
                main(["買い見ます"])
            self.assertEqual(error.exception.code, 2)
            self.assertIn(message, stderr.getvalue())
