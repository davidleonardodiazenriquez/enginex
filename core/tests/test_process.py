from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class ProcessWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="process-viewer")

    def test_requires_an_authenticated_workspace_session(self):
        response = self.client.get(reverse("process"))
        self.assertRedirects(response, f"{reverse('login')}?next=/process/")

    def test_process_page_works_without_portfolio_data_or_ai_configuration(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("process"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/process.html")
        self.assertContains(response, 'href="/process/" aria-current="page"')
        self.assertContains(response, "data-process-canvas")
        self.assertContains(response, "process-text-alternative")
        self.assertContains(response, 'href="/contracts/"')
        self.assertContains(response, 'href="/enginex-ai/"')

    def test_walkthrough_accepts_reads_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse("process")).status_code, 405)
