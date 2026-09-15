import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from core.ai.queries import contract_evidence, document_library
from core.documents.association import evaluate_location, resolve_document_location
from core.documents.extraction import claim_run, process_run
from core.documents.services import associate, ingest_pdf, queue_extraction
from core.models import (
    Asset,
    ContractDocument,
    ExtractedField,
    ExtractionRun,
    LeaseRecord,
)
from core.tests.support import FOUNDRY_SETTINGS
from core.tests.test_contracts import fixture_pdf


class LocationAssociationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username="location-reviewer")
        cls.assets = [Asset.objects.create(name=name, location="Abu Dhabi", asset_class="Residential",
            developer="Aldar", buildings=1, units=10, unit_mix="Apartments", amenities="Parking")
            for name in ("Eastern Mangroves", "Al Rayyana", "Gate", "Arc", "The Bridges II")]

    def setUp(self):
        self.client.force_login(self.user)

    def document(self, values=("Eastern Mangroves, Abu Dhabi, UAE",), *, document=None):
        if document is None:
            index = ContractDocument.objects.count() + 1
            record = LeaseRecord.objects.create(code=f"DOC-LOCATION-{index}", origin="document")
            document = ContractDocument.objects.create(record=record, title="contract.pdf", sha256=f"{index:064x}",
                storage_key="local:fixture", size_bytes=100, page_count=1)
        quotes = [f"Location: {value}." for value in values]
        run = ExtractionRun.objects.create(document=document, status="completed", pages=[{"page": 1, "text": "\n".join(quotes)}])
        for value, quote in zip(values, quotes, strict=True):
            ExtractedField.objects.create(run=run, name="property_location", value=value, quote=quote, page=1)
        return document, run

    def test_clear_match_links_own_record_and_keeps_evidence_and_history(self):
        document, run = self.document()
        record_id = document.record_id
        self.assertEqual(resolve_document_location(document.pk), "automatic")
        document.refresh_from_db()
        self.assertEqual(document.record_id, record_id)
        self.assertEqual(document.record.asset_id, self.assets[0].pk)
        self.assertEqual(document.record.data, {})
        self.assertEqual(run.fields.get().review_status, "pending")
        event = document.associations.get()
        self.assertEqual(event.method, "automatic")
        self.assertIsNone(event.user_id)
        self.assertEqual(event.evidence[0]["field_id"], run.fields.get().pk)
        self.assertEqual(event.evidence[0]["quote"], run.fields.get().quote)
        self.assertEqual(contract_evidence({})["rows"][0]["association_status"], "Linked automatically")
        library = document_library({})["rows"][0]
        self.assertEqual(library["association_status"], "Linked automatically")
        self.assertEqual(library["associations"][0]["method"], "automatic")
        resolve_document_location(document.pk)
        self.assertEqual(document.associations.count(), 1)

    def test_case_punctuation_and_explicit_phase_aliases(self):
        cases = [("EASTERN—MANGROVES, Abu Dhabi", "Eastern Mangroves"), ("Al-Rayyana", "Al Rayyana"),
                 ("Gate Towers, Al Reem Island", "Gate"), ("The Arc, Abu Dhabi", "Arc"),
                 ("The Bridges 2, Abu Dhabi", "The Bridges II")]
        for value, expected in cases:
            with self.subTest(value=value):
                _, run = self.document((value,))
                result = evaluate_location(run, self.assets)
                self.assertEqual(result["status"], "automatic")
                self.assertEqual(Asset.objects.get(pk=result["asset_id"]).name, expected)

    def test_unknown_ambiguous_relative_and_generic_names_require_review(self):
        cases = [("KEZAD KLP 1, Unit A-23",), ("Gardenia-Lilac-B6",), ("The Bridges",),
                 ("Entrance gate 3",), ("Entrance through the gate 3",), ("Arcadia Road",), ("Near Eastern Mangroves",),
                 ("Not Al Rayyana",), ("Landlord address: Eastern Mangroves",),
                 ("Eastern Mangroves", "Al Rayyana"), ("Eastern Mangroves", "Gardenia")]
        for values in cases:
            with self.subTest(values=values):
                document, _ = self.document(values)
                self.assertEqual(resolve_document_location(document.pk), "review")
                document.refresh_from_db()
                self.assertIsNone(document.record.asset_id)

    def test_filename_and_non_premises_fields_do_not_create_a_match(self):
        document, run = self.document(("KEZAD KLP 1",))
        document.title = "Eastern Mangroves.pdf"
        document.save(update_fields=["title"])
        ExtractedField.objects.create(run=run, name="landlord", value="Eastern Mangroves", quote="Eastern Mangroves", page=1)
        self.assertEqual(resolve_document_location(document.pk), "review")

    def test_party_address_mislabelled_as_premises_is_not_auto_linked(self):
        document, run = self.document()
        quote = "Landlord: Eastern Mangroves, Abu Dhabi, UAE"
        run.pages = [{"page": 1, "text": quote}]
        run.save(update_fields=["pages"])
        run.fields.update(quote=quote)
        self.assertEqual(resolve_document_location(document.pk), "review")

    def test_invalid_or_rejected_page_evidence_needs_review(self):
        for change in ({"page": 2}, {"quote": "A quotation missing from the PDF"}, {"review_status": "rejected"}):
            with self.subTest(change=change):
                document, run = self.document()
                run.fields.update(**change)
                self.assertEqual(resolve_document_location(document.pk), "review")

    def test_missing_extraction_is_pending_and_empty_premises_need_review(self):
        document, run = self.document(())
        self.assertEqual(resolve_document_location(document.pk), "review")
        run.delete()
        self.assertEqual(resolve_document_location(document.pk), "pending")

    def test_manual_and_legacy_outside_decisions_are_preserved(self):
        for asset in (self.assets[1], None):
            with self.subTest(asset=asset):
                document, _ = self.document()
                associate(document, document.record, asset, "Reviewed manually from the source PDF.", self.user)
                # Simulate a decision from before the status fields were introduced.
                ContractDocument.objects.filter(pk=document.pk).update(association_status="pending", association_details={})
                status = resolve_document_location(document.pk)
                document.refresh_from_db()
                self.assertEqual(status, "manual" if asset else "outside")
                self.assertEqual(document.record.asset_id, asset.pk if asset else None)
                self.assertEqual(document.associations.count(), 1)

    def test_shared_or_baseline_records_are_not_moved_automatically(self):
        document, _ = self.document()
        ContractDocument.objects.create(record=document.record, title="other.pdf", sha256="f" * 64,
            storage_key="local:fixture2", size_bytes=100, page_count=1)
        self.assertEqual(resolve_document_location(document.pk), "review")
        record = document.record
        record.origin = "synthetic"
        record.save(update_fields=["origin"])
        self.assertEqual(resolve_document_location(document.pk), "review")
        record.refresh_from_db()
        self.assertIsNone(record.asset_id)

    def test_latest_conflicting_extraction_withdraws_only_automatic_link(self):
        document, _ = self.document()
        resolve_document_location(document.pk)
        self.document(("Eastern Mangroves", "Al Rayyana"), document=document)
        self.assertEqual(resolve_document_location(document.pk), "review")
        document.refresh_from_db()
        self.assertIsNone(document.record.asset_id)
        self.assertEqual(document.associations.count(), 2)
        self.assertIn("withdrawn", document.associations.first().reason)

    def test_retry_after_matching_error_keeps_automatic_ownership(self):
        document, _ = self.document()
        resolve_document_location(document.pk)
        self.document(("Eastern Mangroves", "Al Rayyana"), document=document)
        ContractDocument.objects.filter(pk=document.pk).update(association_status="review")
        self.assertEqual(resolve_document_location(document.pk), "review")
        document.refresh_from_db()
        self.assertIsNone(document.record.asset_id)

    def test_rejecting_premises_returns_automatic_link_to_review(self):
        document, run = self.document()
        resolve_document_location(document.pk)
        self.client.post(f"/evidence/{run.fields.get().pk}/review/", {"decision": "rejected"})
        document.refresh_from_db()
        self.assertEqual(document.association_status, "review")
        self.assertIsNone(document.record.asset_id)

    def test_review_queue_and_manual_decision_flow(self):
        document, _ = self.document(("KEZAD KLP 1",))
        resolve_document_location(document.pk)
        response = self.client.get("/contracts/?association=review")
        self.assertEqual([item.pk for item in response.context["documents"]], [document.pk])
        response = self.client.get(f"/contracts/{document.pk}/")
        self.assertContains(response, 'data-location-decision="review"')
        self.assertContains(response, 'id="association-panel" open')
        self.client.post(f"/contracts/{document.pk}/associate/", {"record": document.record_id, "asset": "", "reason": "Premises are KEZAD, outside this portfolio."})
        document.refresh_from_db()
        self.assertEqual(document.association_status, "outside")
        self.assertEqual(self.client.get("/contracts/?association=review").context["documents"], [])

    @override_settings(DEBUG=True, AZURE_STORAGE_ACCOUNT_NAME="", AZURE_STORAGE_ACCOUNT_KEY="", **FOUNDRY_SETTINGS)
    def test_new_extraction_automatically_resolves_location_without_merging_units(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            document, _ = ingest_pdf(fixture_pdf(), "contract.pdf", self.user)
            queue_extraction(document, self.user)
            run = claim_run()
            result = {"fields": [{"name": "property_location", "value": "Al Rayyana", "quote": "Location: Al Rayyana.", "page": 1}], "warnings": []}
            with patch("core.documents.extraction.extract_contract_fields", return_value=result):
                process_run(run)
            run.refresh_from_db()
            document.refresh_from_db()
            self.assertEqual(run.status, "completed")
            self.assertEqual(document.association_status, "automatic")
            self.assertEqual(document.record.asset_id, self.assets[1].pk)
            self.assertEqual(document.record.data, {})

    @override_settings(DEBUG=True, AZURE_STORAGE_ACCOUNT_NAME="", AZURE_STORAGE_ACCOUNT_KEY="", **FOUNDRY_SETTINGS)
    def test_matching_error_does_not_discard_successful_extraction(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            document, _ = ingest_pdf(fixture_pdf(), "contract.pdf", self.user)
            queue_extraction(document, self.user)
            run = claim_run()
            result = {"fields": [{"name": "property_location", "value": "Al Rayyana", "quote": "Location: Al Rayyana.", "page": 1}], "warnings": []}
            with patch("core.documents.extraction.extract_contract_fields", return_value=result), patch("core.documents.extraction.resolve_document_location", side_effect=RuntimeError):
                process_run(run)
            run.refresh_from_db()
            document.refresh_from_db()
            self.assertEqual(run.status, "completed")
            self.assertEqual(run.fields.count(), 1)
            self.assertEqual(document.association_status, "review")
