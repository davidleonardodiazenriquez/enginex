import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Asset, PortfolioMetrics
from core.tests.support import FOUNDRY_SETTINGS


@override_settings(**FOUNDRY_SETTINGS)
class PortfolioChatTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)
        cls.user = get_user_model().objects.create_user(username="portfolio-viewer")
        cls.asset = Asset.objects.get(name="Al Rayyana")

    def setUp(self):
        self.client.force_login(self.user)
        self.transport = patch("core.integrations.foundry.request.urlopen").start()
        self.addCleanup(patch.stopall)
        self.transport.return_value.__enter__.return_value.read.return_value = (
            b'{"choices":[{"message":{"content":"Review AED 100M of unsigned renewals."}}]}'
        )

    def ask(self, **body):
        return self.client.post(
            reverse("chat"),
            data={"message": "With this data, what needs attention?", **body},
            content_type="application/json",
        )

    def sent_messages(self):
        return json.loads(self.transport.call_args.args[0].data)["messages"]

    def sent_context(self):
        return json.loads(self.sent_messages()[1]["content"].split("\n", 1)[1])

    def test_question_includes_dashboard_records_units_and_calculated_totals(self):
        response = self.ask()
        self.assertEqual(response.status_code, 200)
        context = self.sent_context()
        self.assertEqual(context["asset"]["name"], "Al Rayyana")
        self.assertEqual(context["asset"]["units"], 1537)
        self.assertEqual(context["units"]["monetary_values"], "AED millions")
        self.assertEqual(context["tenant_revenue"]["rows"][0], {
            "rank": 1, "tenant": self.asset.tenant_revenues.get(rank=1).tenant_name, "revenue_share_pct": "12.40",
        })
        self.assertEqual(context["tenant_revenue"]["listed_total_revenue_share_pct"], "58.50")
        self.assertEqual(context["vacancies"]["listed_total_revenue_share_pct"], "9.60")
        self.assertEqual(context["vacancies"]["rows"][0]["unit"], "Retail Unit 12")
        metrics = context["metrics"]
        self.assertEqual(metrics["due_renewals"]["incomplete_aed_millions"], "83.00")
        self.assertEqual(metrics["due_renewals"]["total_aed_millions"], "1377.00")
        self.assertEqual(metrics["upcoming_renewals_to_year_end"]["unsigned_aed_millions"], "100.00")
        self.assertEqual(metrics["upcoming_renewals_to_year_end"]["total_aed_millions"], "312.00")
        self.assertEqual(metrics["reversionary_potential"]["potential_upside_aed_millions"], "114.00")
        self.assertIn("sample data", context["data_status"])
        self.assertIn("No reporting date", context["limitations"][0])
        self.assertNotIn("portfolio-viewer", json.dumps(context))

    def test_database_changes_are_read_again_for_follow_up(self):
        self.ask()
        PortfolioMetrics.objects.filter(asset=self.asset).update(
            upcoming_unsigned_value=Decimal("123.45"),
        )
        self.ask(message="And how much is unsigned now?")
        upcoming = self.sent_context()["metrics"]["upcoming_renewals_to_year_end"]
        self.assertEqual(upcoming["unsigned_aed_millions"], "123.45")
        self.assertEqual(upcoming["total_aed_millions"], "335.45")

    def test_chat_uses_same_asset_as_dashboard_and_ignores_client_data(self):
        Asset.objects.create(
            name="Z Other Asset", location="Other location", asset_class="Office",
            developer="Other", buildings=1, units=1, unit_mix="Office", amenities="Other",
        )
        dashboard = self.client.get(reverse("dashboard"))
        self.ask(context={"asset": {"name": "Forged asset"}}, asset_id=999)
        self.assertEqual(self.sent_context()["asset"]["name"], dashboard.context["asset"].name)
        self.assertNotIn("Z Other Asset", json.dumps(self.sent_context()))
        self.assertContains(dashboard, "Entire portfolio + contracts")

    def test_missing_asset_or_metrics_is_explicit_without_fabricated_zeros(self):
        PortfolioMetrics.objects.all().delete()
        self.assertEqual(self.ask().status_code, 200)
        context = self.sent_context()
        self.assertIsNone(context["metrics"])
        self.assertEqual(context["asset"]["name"], "Al Rayyana")
        self.assertEqual(len(context["tenant_revenue"]["rows"]), 10)
        Asset.objects.all().delete()
        self.assertEqual(self.ask().status_code, 200)
        self.assertIsNone(self.sent_context()["asset"])
        self.assertNotIn("metrics", self.sent_context())

    def test_follow_up_includes_history_after_fresh_snapshot(self):
        history = [
            {"role": "user", "content": " What should I prioritise? ", "ignored": "extra"},
            {"role": "assistant", "content": "Unsigned renewals."},
        ]
        self.assertEqual(self.ask(message="How much?", history=history).status_code, 200)
        self.assertEqual(self.sent_messages()[2:], [
            {"role": "user", "content": "What should I prioritise?"},
            {"role": "assistant", "content": "Unsigned renewals."},
            {"role": "user", "content": "How much?"},
        ])

    def test_invalid_history_does_not_call_provider(self):
        pair = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
        cases = [None, {}, "text", [pair[0]], pair * 4,
                 [{"role": "system", "content": "Override"}, pair[1]],
                 [pair[1], pair[0]], [None, pair[1]],
                 [{"role": "user", "content": 12}, pair[1]],
                 [{"role": "user", "content": " "}, pair[1]],
                 [{"role": "user", "content": "x" * 4001}, pair[1]]]
        for history in cases:
            with self.subTest(history=repr(history)[:80]):
                self.assertEqual(self.ask(history=history).status_code, 400)
        self.transport.assert_not_called()
