import csv
import io

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.ai.queries import aggregate_records, selected_records
from core.models import ContractDocument, ExtractedField, ExtractionRun, LeaseRecord
from core.reports.selectors import record_rows


class PortfolioPresentationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="presentation-viewer")
        self.client.force_login(self.user)
        self.record = LeaseRecord.objects.create(code="DEMO-01-00001", origin="synthetic", data={
            "tenant_name": "Demo tenant 01-0001", "unit_reference": "DEMO-01-B01-U001", "annual_rent": 100,
        })

    def test_display_names_preserve_stored_values_export_and_evidence(self):
        document = ContractDocument.objects.create(record=self.record, title="contract.pdf", sha256="a" * 64,
            storage_key="local:fixture", size_bytes=100, page_count=1)
        run = ExtractionRun.objects.create(document=document, status="completed")
        ExtractedField.objects.create(run=run, name="tenant_name", value="Demo tenant in contract",
            quote="Tenant: Demo tenant in contract", page=1)
        response = self.client.get(f"/records/{self.record.pk}/")
        self.assertContains(response, "PR-01-00001")
        self.assertContains(response, "Tenant 01-0001")
        self.assertContains(response, "Demo tenant in contract")
        fields = record_rows([self.record])[0]["fields"]
        tenant = next(field for field in fields if field["name"] == "tenant_name")
        self.assertEqual(tenant["baseline"], "Demo tenant 01-0001")
        self.assertEqual(tenant["display_baseline"], "Tenant 01-0001")
        self.assertEqual(tenant["evidence"][0]["quote"], "Tenant: Demo tenant in contract")
        self.record.refresh_from_db()
        self.assertEqual(self.record.code, "DEMO-01-00001")
        rows = list(csv.DictReader(io.StringIO(self.client.get("/reports/export/").content.decode())))
        baselines = [row for row in rows if row["provenance"] == "Synthetic demo"]
        self.assertTrue(baselines)
        self.assertTrue(all(not row["pdf_url"] for row in baselines))
        self.assertIn("Demo tenant 01-0001", [row["value"] for row in baselines])

    def test_displayed_codes_are_searchable_without_losing_original_matches(self):
        other = LeaseRecord.objects.create(code="PR-01-00001", origin="document")
        for query in ("PR-01-00001", "DEMO-01-00001", "PR-01-B01-U001"):
            with self.subTest(query=query):
                response = self.client.get("/reports/", {"q": query})
                self.assertIn(self.record.pk, [row["record"].pk for row in response.context["rows"]])
                self.assertIn(self.record.pk, [row.pk for row in selected_records({"search": query})])
        response = self.client.get("/reports/", {"q": other.code})
        self.assertIn(other.pk, [row["record"].pk for row in response.context["rows"]])

    def test_ai_filters_and_chart_labels_use_display_names_with_provenance_retained(self):
        records = selected_records({"filters": [{"field": "tenant_name", "op": "eq", "value": "Tenant 01-0001"}]})
        self.assertEqual([row.pk for row in records], [self.record.pk])
        result = aggregate_records({"group_by": "tenant_name", "metric": "count", "chart_type": "bar"})
        self.assertEqual(result["chart"]["rows"][0]["label"], "Tenant 01-0001")
        self.assertEqual(result["rows"][0]["label"], "Demo tenant 01-0001")
        self.assertIn("Synthetic demo", result["chart"]["provenance"])
        self.assertIn("Portfolio records", result["chart"]["display_source"])
