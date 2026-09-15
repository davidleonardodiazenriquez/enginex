import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core import foundry

FOUNDRY_SETTINGS = {
    "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.openai.azure.com/openai/v1/",
    "AZURE_AI_FOUNDRY_API_KEY": "test-provider-key",
    "AZURE_AI_FOUNDRY_DEPLOYMENT": "gpt-6-astra",
    "AZURE_AI_FOUNDRY_API_VERSION": "2024-10-21",
}


class CoreViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = get_user_model().objects.create_user(
            username="viewer", password="safe-test-password"
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_login_page_is_available(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in to your workspace")

    def test_authenticated_dashboard_renders_database_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Al Rayyana")
        self.assertContains(response, "Tenant A")

    def test_unconfigured_chat_returns_service_unavailable(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("chat"),
            data=json.dumps({"message": "Summarize the portfolio"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "Azure AI Foundry is not configured."})

    def test_health_reports_healthy(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})


@override_settings(**FOUNDRY_SETTINGS)
class FoundryTransportTests(SimpleTestCase):
    @patch("core.foundry.request.urlopen")
    def test_supported_endpoint_formats(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":"OK"}}]}'
        )
        cases = [
            ("https://example.openai.azure.com/openai/v1/", "2024-10-21",
             "https://example.openai.azure.com/openai/v1/chat/completions"),
            ("https://example.openai.azure.com/openai/v1", "2024-10-21",
             "https://example.openai.azure.com/openai/v1/chat/completions"),
            ("https://example.openai.azure.com/openai/v1/chat/completions/", "2024-10-21",
             "https://example.openai.azure.com/openai/v1/chat/completions"),
            ("https://example.openai.azure.com/openai/v1/chat/completions?api-version=preview", "2024-10-21",
             "https://example.openai.azure.com/openai/v1/chat/completions?api-version=preview"),
            ("https://example.services.ai.azure.com/api/projects/demo/openai/v1", "2024-10-21",
             "https://example.services.ai.azure.com/api/projects/demo/openai/v1/chat/completions"),
            ("https://example.openai.azure.com/", "2024-10-21",
             "https://example.openai.azure.com/openai/deployments/gpt-6-astra/chat/completions?api-version=2024-10-21"),
            ("https://example.openai.azure.com/openai/", "2024-10-21",
             "https://example.openai.azure.com/openai/deployments/gpt-6-astra/chat/completions?api-version=2024-10-21"),
            ("https://example.openai.azure.com", "v1",
             "https://example.openai.azure.com/openai/v1/chat/completions"),
            ("https://example.openai.azure.com", "preview",
             "https://example.openai.azure.com/openai/v1/chat/completions?api-version=preview"),
            ("https://example.openai.azure.com/openai/deployments/custom/chat/completions?api-version=2025-01-01-preview&extra=1", "2024-10-21",
             "https://example.openai.azure.com/openai/deployments/custom/chat/completions?api-version=2025-01-01-preview&extra=1"),
        ]
        for endpoint, version, expected_url in cases:
            with self.subTest(endpoint=endpoint, version=version), override_settings(
                AZURE_AI_FOUNDRY_ENDPOINT=endpoint,
                AZURE_AI_FOUNDRY_API_VERSION=version,
            ):
                self.assertTrue(foundry.is_configured())
                self.assertEqual(foundry.get_answer("Hello"), "OK")
                self.assertEqual(urlopen.call_args.args[0].full_url, expected_url)

    @patch("core.foundry.request.urlopen")
    def test_v1_payload_supports_reasoning_and_custom_deployment_names(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":"OK"}}]}'
        )
        for deployment in ["gpt-6-astra", "our-hackathon-model"]:
            with self.subTest(deployment=deployment), override_settings(
                AZURE_AI_FOUNDRY_DEPLOYMENT=deployment
            ):
                foundry.get_answer("Hello")
                outgoing = urlopen.call_args.args[0]
                payload = json.loads(outgoing.data)
                self.assertEqual(payload["model"], deployment)
                self.assertEqual(payload["messages"][-1], {"role": "user", "content": "Hello"})
                self.assertEqual(payload["max_completion_tokens"], 4096)
                self.assertNotIn("max_tokens", payload)
                self.assertNotIn("temperature", payload)
                self.assertEqual(outgoing.get_header("Api-key"), "test-provider-key")
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 45)

    @override_settings(
        AZURE_AI_FOUNDRY_ENDPOINT="https://example.openai.azure.com/",
        AZURE_AI_FOUNDRY_DEPLOYMENT="gpt-4o",
    )
    @patch("core.foundry.request.urlopen")
    def test_legacy_payload_remains_supported(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":"Legacy answer"}}]}'
        )
        self.assertEqual(foundry.get_answer("Hello"), "Legacy answer")
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["max_tokens"], 700)
        self.assertEqual(payload["temperature"], 0.2)
        self.assertNotIn("model", payload)

    def test_incomplete_and_invalid_configurations_are_not_ready(self):
        cases = [
            {"AZURE_AI_FOUNDRY_ENDPOINT": ""},
            {"AZURE_AI_FOUNDRY_API_KEY": "  "},
            {"AZURE_AI_FOUNDRY_DEPLOYMENT": ""},
            {"AZURE_AI_FOUNDRY_ENDPOINT": "not-a-url"},
            {"AZURE_AI_FOUNDRY_ENDPOINT": "https://example.openai.azure.com/unsupported"},
        ]
        for settings in cases:
            with self.subTest(settings=settings), override_settings(**settings):
                self.assertFalse(foundry.is_configured())

    @override_settings(
        AZURE_AI_FOUNDRY_ENDPOINT="https://example.openai.azure.com/openai/deployments/legacy/chat/completions",
        AZURE_AI_FOUNDRY_DEPLOYMENT="",
    )
    def test_full_legacy_url_can_supply_the_deployment(self):
        self.assertTrue(foundry.is_configured())

    @patch("core.foundry.request.urlopen")
    def test_invalid_or_empty_provider_responses_are_unavailable(self, urlopen):
        results = [b"not JSON", b"null", b"{}", b'{"choices":[]}',
                   b'{"choices":[{"message":{"content":null}}]}',
                   b'{"choices":[{"message":{"content":"  "}}]}']
        for response in results:
            with self.subTest(response=response):
                urlopen.return_value.__enter__.return_value.read.return_value = response
                with self.assertLogs("core.foundry", level="WARNING"):
                    with self.assertRaises(foundry.FoundryUnavailable):
                        foundry.get_answer("Hello")

    @patch("core.foundry.request.urlopen")
    def test_http_errors_log_diagnostics_without_provider_messages_or_credentials(self, urlopen):
        body = json.dumps({"error": {
            "code": "unsupported_parameter", "param": "max_tokens",
            "message": "Sensitive prompt and test-provider-key",
        }}).encode()
        urlopen.side_effect = HTTPError("https://example/", 400, "Bad Request", {}, BytesIO(body))
        with self.assertLogs("core.foundry", level="WARNING") as captured:
            with self.assertRaises(foundry.FoundryUnavailable):
                foundry.get_answer("Private prompt")
        logs = " ".join(captured.output)
        self.assertIn("http_status=400", logs)
        self.assertIn("error_code=unsupported_parameter", logs)
        self.assertIn("parameter=max_tokens", logs)
        for private_value in ["Sensitive prompt", "test-provider-key", "Private prompt"]:
            self.assertNotIn(private_value, logs)

    @patch("core.foundry.request.urlopen")
    def test_network_timeouts_and_non_json_http_errors_are_unavailable(self, urlopen):
        for problem in [TimeoutError(), URLError("connection failed"),
                        HTTPError("https://example/", 502, "Bad Gateway", {}, BytesIO(b"<html>error</html>"))]:
            with self.subTest(problem=type(problem).__name__):
                urlopen.side_effect = problem
                with self.assertLogs("core.foundry", level="WARNING"):
                    with self.assertRaises(foundry.FoundryUnavailable):
                        foundry.get_answer("Hello")

    @patch("core.foundry.request.urlopen")
    def test_provider_error_identifiers_are_sanitized(self, urlopen):
        body = json.dumps({"error": {
            "code": "test-provider-key", "param": "unexpected\nlog line",
        }}).encode()
        urlopen.side_effect = HTTPError("https://example/", 401, "Unauthorized", {}, BytesIO(body))
        with self.assertLogs("core.foundry", level="WARNING") as captured:
            with self.assertRaises(foundry.FoundryUnavailable):
                foundry.get_answer("Hello")
        self.assertIn("error_code=redacted parameter=unknown", captured.output[0])
        self.assertNotIn("test-provider-key", captured.output[0])


@override_settings(**FOUNDRY_SETTINGS)
class ChatEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="chat-viewer")

    def setUp(self):
        self.client.force_login(self.user)

    @patch("core.foundry.request.urlopen")
    def test_authenticated_chat_returns_provider_answer(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":"Review upcoming renewals."}}]}'
        )
        response = self.client.post(reverse("chat"), data={"message": "  Help me  "}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "Review upcoming renewals."})
        self.assertEqual(json.loads(urlopen.call_args.args[0].data)["messages"][-1]["content"], "Help me")

    @patch("core.foundry.request.urlopen")
    def test_invalid_requests_do_not_call_provider(self, urlopen):
        bodies = ["{", "[]", "null", "{}", '{"message":null}', '{"message":123}',
                  '{"message":"  "}', json.dumps({"message": "x" * 4001})]
        for body in bodies:
            with self.subTest(body=body[:40]):
                response = self.client.post(reverse("chat"), data=body, content_type="application/json")
                self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse("chat"), data=b"\xff", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        urlopen.assert_not_called()

    @patch("core.foundry.request.urlopen")
    def test_provider_failure_returns_safe_error(self, urlopen):
        urlopen.side_effect = TimeoutError("private transport details")
        with self.assertLogs("core.foundry", level="WARNING"):
            response = self.client.post(reverse("chat"), data={"message": "Hello"}, content_type="application/json")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "The AI assistant is temporarily unavailable."})

    @patch("core.foundry.request.urlopen")
    def test_chat_requires_login_and_post(self, urlopen):
        self.assertEqual(self.client.get(reverse("chat")).status_code, 405)
        self.client.logout()
        response = self.client.post(reverse("chat"), data={"message": "Hello"}, content_type="application/json")
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        urlopen.assert_not_called()

    def test_dashboard_does_not_claim_connectivity_from_configuration(self):
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "Entire portfolio + contracts")
        self.assertNotContains(response, "Connected to Azure AI Foundry")
