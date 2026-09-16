import io
import json
from unittest.mock import patch
from urllib.error import HTTPError

from django.test import SimpleTestCase, override_settings

from core.ai import responses, service
from core.integrations import foundry
from core.tests.support import FOUNDRY_SETTINGS


@override_settings(**FOUNDRY_SETTINGS)
class ResponsesTransportTests(SimpleTestCase):
    def test_endpoint_forms_keep_the_configured_resource_and_model(self):
        for endpoint, expected in [
            ("https://example.openai.azure.com", "https://example.openai.azure.com/openai/v1/responses"),
            ("https://example.openai.azure.com/openai/v1/", "https://example.openai.azure.com/openai/v1/responses"),
            ("https://example.openai.azure.com/openai/v1/chat/completions?api-version=preview", "https://example.openai.azure.com/openai/v1/responses?api-version=preview"),
            ("https://example.services.ai.azure.com/api/projects/enginex/openai/v1", "https://example.services.ai.azure.com/api/projects/enginex/openai/v1/responses"),
        ]:
            with self.subTest(endpoint=endpoint), override_settings(AZURE_AI_FOUNDRY_ENDPOINT=endpoint):
                url, payload = responses.request_payload([{"role": "user", "content": "Hello"}], allow_tools=True)
                self.assertEqual(url, expected)
                self.assertEqual(payload["model"], FOUNDRY_SETTINGS["AZURE_AI_FOUNDRY_DEPLOYMENT"])

    @patch("core.ai.service.request.urlopen")
    def test_incomplete_empty_and_invalid_results_fail_without_a_fabricated_answer(self, urlopen):
        for body in [None, {}, {"status": "incomplete", "output": []}, {"status": "failed", "output": []},
                     {"status": "completed", "output": []}, {"status": "completed", "output": [
                         {"type": "function_call", "name": "aggregate_records", "arguments": "{}"}]}]:
            with self.subTest(body=body):
                urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(body)
                with self.assertLogs("core.ai.service", level="WARNING"), self.assertRaises(foundry.FoundryUnavailable):
                    service.completion([{"role": "user", "content": "Hello"}])

    def test_refusal_is_displayed_as_text(self):
        result = responses.parse_reply({"status": "completed", "output": [{"type": "message", "content": [
            {"type": "refusal", "refusal": "I cannot do that."}]}]})
        self.assertEqual(result["content"], "I cannot do that.")

    @patch("core.ai.service.request.urlopen")
    def test_provider_failure_logs_identifiers_without_sensitive_content(self, urlopen):
        body = {"error": {"code": "unsupported_value", "param": "reasoning_effort",
                          "message": "Private prompt and test-provider-key"}}
        urlopen.side_effect = HTTPError("https://example.openai.azure.com", 400, "Bad request", {}, io.BytesIO(json.dumps(body).encode()))
        with self.assertLogs("core.ai.service", level="WARNING") as logs, self.assertRaises(foundry.FoundryUnavailable):
            service.completion([{"role": "user", "content": "Private prompt"}])
        self.assertIn("status=400 code=unsupported_value parameter=reasoning_effort", logs.output[0])
        self.assertNotIn("Private prompt", logs.output[0])
        self.assertNotIn("test-provider-key", logs.output[0])

    @override_settings(AZURE_AI_FOUNDRY_DEPLOYMENT="gpt-4.1")
    @patch("core.ai.service.request.urlopen")
    def test_other_deployments_keep_chat_completions(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({
            "choices": [{"finish_reason": "stop", "message": {"content": "Ready"}}]})
        self.assertEqual(service.completion([{"role": "user", "content": "Hello"}])["content"], "Ready")
        self.assertTrue(urlopen.call_args.args[0].full_url.endswith("/chat/completions"))
        self.assertIn("messages", json.loads(urlopen.call_args.args[0].data))
