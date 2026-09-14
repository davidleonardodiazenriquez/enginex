from django.test import TestCase
from django.urls import reverse


class CoreViewsTests(TestCase):
    def test_home_reports_application_status(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"application": "enginex", "status": "running"})

    def test_health_reports_healthy(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy"})
