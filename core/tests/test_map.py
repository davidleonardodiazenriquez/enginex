from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import Asset, TenantRevenue


class PortfolioMapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = get_user_model().objects.create_user(username="map-viewer")

    def test_map_requires_login(self):
        self.assertRedirects(self.client.get("/"), "/login/?next=/")

    def test_map_lists_six_locations_and_only_links_existing_metrics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("portfolio"))
        self.assertEqual(response.status_code, 200)
        locations = response.context["locations"]
        self.assertEqual([row["name"] for row in locations], [
            "Al Rayyana", "Gate", "Arc", "The Bridges II", "Sas Al Nakhl", "Eastern Mangroves",
        ])
        self.assertEqual(response.context["ready_count"], 1)
        self.assertEqual(locations[0]["metrics_url"], "/assets/al-rayyana/")
        self.assertEqual(locations[0]["facts"][0]["value"], "1,537")
        for row in locations[1:]:
            self.assertFalse(row["ready"])
            self.assertIsNone(row["metrics_url"])
            self.assertEqual(row["facts"], [])
        self.assertEqual(Asset.objects.count(), 1)

    def test_metrics_remain_available_with_return_to_map(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, TenantRevenue.objects.get(rank=1).tenant_name)
        self.assertContains(response, '<a href="/">← Portfolio map</a>', html=True)
        self.assertEqual(response.context["asset"].name, "Al Rayyana")

    def test_other_assets_cannot_substitute_for_al_rayyana(self):
        Asset.objects.filter(name="Al Rayyana").update(name="A Different Asset")
        self.client.force_login(self.user)
        response = self.client.get(reverse("portfolio"))
        self.assertEqual(response.context["ready_count"], 0)
        self.assertTrue(all(not row["ready"] for row in response.context["locations"]))
        self.assertIsNone(self.client.get(reverse("dashboard")).context["asset"])

    def test_login_default_destination_is_map(self):
        from django.conf import settings
        self.assertEqual(reverse(settings.LOGIN_REDIRECT_URL), "/")
