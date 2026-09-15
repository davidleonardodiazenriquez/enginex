from unittest.mock import patch

from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase, override_settings

from core.models import ContractDocument, ExtractedField, ExtractionRun, LeaseRecord
from core.tests.support import FOUNDRY_SETTINGS


@override_settings(DEBUG=True, LOCAL_DEMO_AUTO_LOGIN=True)
class LocalDemoLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.demo = get_user_model().objects.create_user(username="demo")

    def test_fresh_visit_opens_map_and_keeps_demo_session(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.user.pk, self.demo.pk)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.demo.pk))
        session_key = self.client.session.session_key
        self.assertEqual(self.client.get("/reports/").status_code, 200)
        self.assertEqual(self.client.session.session_key, session_key)
        self.assertNotContains(response, "Sign out")

    def test_direct_links_open_without_login(self):
        for path in ("/assets/al-rayyana/", "/reports/", "/contracts/", "/enginex-ai/"):
            with self.subTest(path=path):
                response = Client().get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.wsgi_request.user.pk, self.demo.pk)
                self.assertNotContains(response, "Sign out")
        self.assertRedirects(Client().get("/login/"), "/")

    @override_settings(**FOUNDRY_SETTINGS)
    @patch("core.ai.views.analyst.answer", return_value={"answer": "Portfolio ready", "charts": []})
    def test_browser_can_send_chat_with_automatically_created_session(self, answer):
        client = Client(enforce_csrf_checks=True)
        client.get("/enginex-ai/")
        response = client.post("/api/enginex-ai/", {"message": "Show the portfolio"},
                               content_type="application/json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer"], "Portfolio ready")
        answer.assert_called_once_with("Show the portfolio", [], None)

    def test_document_review_is_attributed_to_demo(self):
        record = LeaseRecord.objects.create(code="DOC-REVIEW", origin="document")
        document = ContractDocument.objects.create(title="review.pdf", sha256="a" * 64,
            storage_key="local:test", size_bytes=100, page_count=1, record=record)
        run = ExtractionRun.objects.create(document=document, status="completed")
        field = ExtractedField.objects.create(run=run, name="annual_rent", value="AED 100", quote="AED 100", page=1)
        response = self.client.post(f"/evidence/{field.pk}/review/", {"decision": "confirmed"})
        self.assertEqual(response.status_code, 302)
        field.refresh_from_db()
        self.assertEqual(field.reviewed_by_id, self.demo.pk)
        self.assertEqual(field.review_status, "confirmed")

    def test_existing_authenticated_user_is_preserved(self):
        user = get_user_model().objects.create_user(username="existing-user")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/").wsgi_request.user.pk, user.pk)

    def test_admin_login_remains_separate(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_missing_or_inactive_demo_is_reported_and_health_still_works(self):
        self.demo.is_active = False
        self.demo.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/").status_code, 503)
        self.demo.delete()
        self.assertEqual(self.client.get("/").status_code, 503)
        with self.assertNumQueries(0):
            self.assertEqual(self.client.get("/health/").status_code, 200)

    @override_settings(LOCAL_DEMO_AUTO_LOGIN=False)
    def test_disabled_mode_keeps_normal_login(self):
        self.assertRedirects(self.client.get("/"), "/login/?next=/")

    @override_settings(DEBUG=False)
    def test_auto_login_is_not_enabled_outside_development(self):
        self.assertRedirects(self.client.get("/"), "/login/?next=/")


@override_settings(DEBUG=False, LOCAL_DEMO_AUTO_LOGIN=False, DEMO_AUTO_LOGIN=True)
class HostedDemoLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.demo = get_user_model().objects.create_user(username="demo")

    def test_fresh_hosted_visitors_open_workspace_without_credentials(self):
        for path in ("/", "/process/", "/feedback/", "/enginex-ai/", "/reports/"):
            with self.subTest(path=path):
                client = Client()
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.wsgi_request.user.pk, self.demo.pk)
                self.assertFalse(response.wsgi_request.user.is_staff)
                self.assertEqual(client.session[SESSION_KEY], str(self.demo.pk))
                self.assertNotContains(response, "Sign out")
        self.assertRedirects(Client().get("/login/?next=/process/"), "/process/")

    def test_administrator_still_requires_its_own_login(self):
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.client.get("/")
        self.assertRedirects(self.client.get("/admin/"), "/admin/login/?next=/admin/")

    def test_privileged_demo_account_is_never_used_for_public_access(self):
        self.demo.is_staff = True
        self.demo.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get("/").status_code, 503)
        self.assertNotIn(SESSION_KEY, self.client.session)
