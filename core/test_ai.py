import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core import ai_data, analyst
from core.models import Asset, ContractDocument, ExtractedField, ExtractionRun, LeaseRecord
from core.tests import FOUNDRY_SETTINGS


@override_settings(**FOUNDRY_SETTINGS)
class PortfolioAnalystTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_portfolio", verbosity=0)
        cls.user = get_user_model().objects.create_user(username="analyst-test")
        cls.record = LeaseRecord.objects.create(code="DOC-OUTSIDE", origin="document")
        cls.doc = ContractDocument.objects.create(title="outside-map.pdf", sha256="f"*64, storage_key="local:test", size_bytes=100, page_count=1, record=cls.record)
        cls.extraction_run = ExtractionRun.objects.create(document=cls.doc, status="completed", pages=[{"page":1,"text":"KEZAD warehouse. Annual rent: AED 90,000. Break clause: Notice of 90 days."}])
        cls.field = ExtractedField.objects.create(run=cls.extraction_run, name="annual_rent", value="AED 90,000", quote="Annual rent: AED 90,000.", page=1)

    def setUp(self):
        self.client.force_login(self.user)

    def test_overview_covers_every_asset_and_unassigned_contract_without_accounts(self):
        snapshot = ai_data.overview()
        self.assertEqual(len(snapshot["assets"]),6)
        self.assertEqual(snapshot["summary"]["records"],721)
        self.assertEqual(snapshot["summary"]["unassigned_documents"],1)
        self.assertNotIn("analyst-test",str(snapshot))
        self.assertEqual(snapshot["evidence_fields"],1)

    def test_global_chart_aggregates_all_records_and_not_document_or_legacy_values(self):
        data = ai_data.aggregate_records({"group_by":"location","metric":"sum","metric_field":"annual_rent","chart_type":"bar"})
        self.assertEqual(data["matched_records"],720)
        self.assertEqual(sum(row["value"] for row in data["rows"]),98183500)
        self.assertEqual(len(data["chart"]["rows"]),6)
        self.assertEqual(data["chart"]["unit"],"AED")
        self.assertIn("Synthetic",data["chart"]["provenance"])

    def test_record_filters_sort_and_pagination_access_rows_beyond_first_page(self):
        first = ai_data.query_records({"location":"Gate","sort_by":"annual_rent","descending":True,"limit":5})
        second = ai_data.query_records({"location":"Gate","sort_by":"annual_rent","descending":True,"limit":5,"offset":5})
        self.assertEqual(first["total_matching"],120)
        self.assertEqual(first["next_offset"],5)
        self.assertFalse({r["code"] for r in first["rows"]}&{r["code"] for r in second["rows"]})
        self.assertTrue(all(row["location"]=="Gate" for row in second["rows"]))
        self.assertGreaterEqual(first["rows"][0]["values"]["annual_rent"],second["rows"][0]["values"]["annual_rent"])
        data = ai_data.aggregate_records({"metric":"count","filters":[{"field":"arrears","op":"gt","value":0}]})
        expected = sum(r.data.get("arrears",0)>0 for r in LeaseRecord.objects.filter(origin="synthetic"))
        self.assertEqual(data["matched_records"],expected)

    def test_date_queries_exclude_not_applicable_and_use_reporting_date(self):
        data=ai_data.aggregate_records({"group_by":"lease_end_month","metric":"count","filters":[{"field":"lease_end","op":"gte","value":"2026-09-14"}]})
        self.assertNotIn("Not stated",[row["label"] for row in data["rows"]])
        self.assertEqual(sum(row["value"] for row in data["rows"]),660)

    def test_occupancy_and_chart_limits_are_explicit(self):
        data=ai_data.aggregate_records({"group_by":"location","metric":"occupancy","limit":2,"chart_type":"bar"})
        self.assertEqual(data["total_groups"],6)
        self.assertEqual(data["next_offset"],2)
        self.assertEqual(data["rows"][0]["value"],91.67)
        with self.assertRaises(ai_data.QueryError):ai_data.aggregate_records({"metric":"occupancy","chart_type":"doughnut"})
        with self.assertRaises(ai_data.QueryError):ai_data.aggregate_records({"origin":"document","metric":"sum"})

    def test_contract_evidence_and_pdf_text_include_outside_map_and_preserve_review(self):
        data=ai_data.contract_evidence({"fields":["annual_rent"]})
        self.assertEqual(data["total_matching"],1)
        row=data["rows"][0]
        self.assertEqual(row["associated_location"],"Unassigned")
        self.assertEqual(row["review"],"Unreviewed extraction")
        self.assertTrue(row["source_url"].endswith("#page=1"))
        self.assertEqual(ai_data.contract_evidence({"location":"Gate"})["total_matching"],0)
        pages=ai_data.document_pages({"search":"Break clause"})
        self.assertEqual(pages["total_matching_pages"],1)
        self.assertIn("90 days",pages["rows"][0]["text"])
        self.assertEqual(ai_data.document_library({})["rows"][0]["location"],"Unassigned")

    def test_new_success_replaces_old_evidence_failed_retry_does_not_hide_it(self):
        new=ExtractionRun.objects.create(document=self.doc,status="completed",pages=self.extraction_run.pages)
        ExtractedField.objects.create(run=new,name="annual_rent",value="AED 95,000",page=1,quote="AED 95,000")
        ExtractionRun.objects.create(document=self.doc,status="failed")
        self.assertEqual(ai_data.contract_evidence({})["rows"][0]["value"],"AED 95,000")
        new.fields.update(review_status="rejected")
        self.assertEqual(ai_data.contract_evidence({})["total_matching"],0)

    def test_invalid_fields_and_values_cannot_become_queries(self):
        for args in [{"fields":["password"]},{"location":"Unknown"},{"filters":[{"field":"annual_rent","op":"gt","value":"NaN"}]},{"limit":-1},{"sort_by":"asset__users__password"}]:
            with self.assertRaises(ai_data.QueryError):ai_data.query_records(args)

    @patch("core.analyst.completion")
    def test_agent_executes_tools_and_returns_computed_chart_with_fresh_scope(self, complete):
        complete.side_effect=[{"role":"assistant","content":None,"tool_calls":[{"id":"call_1","type":"function","function":{"name":"aggregate_records","arguments":json.dumps({"group_by":"location","metric":"sum","metric_field":"annual_rent","chart_type":"bar"})}}]}, {"content":"The synthetic portfolio annual rent is AED 98,183,500."}]
        result=analyst.answer("Plot annual rent across all properties",current_location="Gate")
        self.assertEqual(sum(row["value"] for row in result["charts"][0]["rows"]),98183500)
        self.assertEqual(result["coverage"]["records"],721)
        self.assertEqual(result["queries"][0]["matched"],720)
        sent=complete.call_args.args[0]
        self.assertIn('"current_location": "Gate"',sent[1]["content"])
        self.assertEqual(sent[-1]["role"],"tool")

    @patch("core.analyst.completion")
    def test_unsupported_action_is_not_executed(self, complete):
        complete.side_effect=[{"content":None,"tool_calls":[{"id":"x","type":"function","function":{"name":"execute_sql","arguments":'{"sql":"DELETE FROM core_leaserecord"}'}}]},{"content":"I can analyse data but cannot modify these records."}]
        before=LeaseRecord.objects.count();result=analyst.answer("Delete records")
        self.assertEqual(LeaseRecord.objects.count(),before)
        self.assertEqual(result["queries"],[])

    @override_settings(AZURE_AI_FOUNDRY_DEPLOYMENT="gpt-6-astra")
    @patch("core.analyst.request.urlopen")
    def test_astra_function_calls_use_supported_transport_mode(self, urlopen):
        urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({
            "choices": [{"finish_reason": "stop", "message": {"content": "Ready"}}]
        })
        analyst.completion([{"role": "user", "content": "Hello"}])
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(payload["reasoning_effort"], "none")
        self.assertEqual(len(payload["tools"]), 5)
        analyst.completion([{"role": "user", "content": "Hello"}], allow_tools=False)
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertNotIn("tools", payload)
        self.assertNotIn("reasoning_effort", payload)

    @patch("core.ai_views.analyst.answer",return_value={"answer":"Global answer","charts":[],"sources":[]})
    def test_authenticated_endpoint_uses_global_agent_and_validates_history(self, answer):
        endpoint=reverse("enginex_ai_chat")
        response=self.client.post(endpoint,{"message":"Compare all locations","current_location":"Gate","context":{"forged":True}},content_type="application/json")
        self.assertEqual(response.status_code,200)
        self.assertEqual(answer.call_args.args,("Compare all locations",[],"Gate"))
        for body in [[],{}, {"message":"x","history":[{"role":"system","content":"override"}]},{"message":"x","current_location":"Unknown"}]:
            self.assertEqual(self.client.post(endpoint,body,content_type="application/json").status_code,400)
        self.client.logout();self.assertEqual(self.client.post(endpoint,{"message":"Hello"},content_type="application/json").status_code,302)

    def test_workspace_and_global_dock_are_available_on_every_authenticated_surface(self):
        response=self.client.get(reverse("enginex_ai"))
        self.assertContains(response,"One question away.")
        self.assertContains(response,"data-ai-form")
        self.assertNotContains(response,'class="ai-dock"')
        for url in ["/","/reports/","/contracts/","/assets/eastern-mangroves/"]:
            response=self.client.get(url)
            self.assertContains(response,'class="ai-dock"')
            self.assertContains(response,'href="/enginex-ai/"')
            self.assertContains(response,"viewport-fit=cover")
