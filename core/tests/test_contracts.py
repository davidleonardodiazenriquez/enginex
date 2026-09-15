import csv
import hashlib
import io
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from core.documents import storage as contract_storage
from core.documents.extraction import claim_run, process_run, validate_fields
from core.documents.services import associate, ingest_pdf, queue_extraction
from core.models import (
    Asset,
    AssociationEvent,
    ContractDocument,
    ExtractedField,
    LeaseRecord,
    PortfolioMetrics,
)
from core.reports.selectors import record_rows
from core.tests.support import FOUNDRY_SETTINGS


def fixture_pdf():
    writer = PdfWriter()
    page = writer.add_blank_page(width=595,height=842)
    font = DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 40 780 Td (SYNTHETIC TEST DOCUMENT. Tenant: Demo Example LLC. Annual rent: AED 120,000.) Tj 0 -20 Td (Location: Al Rayyana. Unit: DEMO-101. This is a unit-test fixture with no live commercial facts.) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    output=io.BytesIO();writer.write(output)
    return output.getvalue()


@override_settings(AZURE_STORAGE_ACCOUNT_NAME='',AZURE_STORAGE_ACCOUNT_KEY='',DEBUG=True,**FOUNDRY_SETTINGS)
class ContractFlowTests(TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        settings_override=override_settings(MEDIA_ROOT=self.directory.name)
        settings_override.enable();self.addCleanup(settings_override.disable)
        self.user=get_user_model().objects.create_user(username='contract-reviewer')
        self.client.force_login(self.user)
        self.pdf=fixture_pdf()

    def import_document(self):
        return ingest_pdf(self.pdf,'anonymized.pdf',self.user)[0]

    def extraction(self,doc):
        run=queue_extraction(doc,self.user)
        self.assertEqual(claim_run().pk,run.pk)
        result={'fields':[{'name':'annual_rent','value':'AED 120,000','page':1,'quote':'Annual rent: AED 120,000.'},{'name':'property_location','value':'Al Rayyana','page':1,'quote':'Location: Al Rayyana.'}], 'warnings':[]}
        with patch('core.documents.extraction.extract_contract_fields',return_value=result):
            process_run(run)
        run.refresh_from_db()
        return run

    def test_upload_extract_associate_report_and_open_source(self):
        response=self.client.post(reverse('contract_ingest'),{'files':SimpleUploadedFile('anonymized.pdf',self.pdf,content_type='application/pdf'),'acknowledge':'yes'})
        doc=ContractDocument.objects.get()
        self.assertRedirects(response,reverse('contract_detail',args=[doc.pk]))
        self.assertIsNone(doc.record.asset)
        run=self.extraction(doc)
        self.assertEqual(run.status,'completed')
        self.assertEqual(run.fields.count(),2)
        self.assertTrue(run.pages)
        asset=Asset.objects.create(name='Al Rayyana',location='Abu Dhabi',asset_class='Residential',developer='Demo',buildings=1,units=10,unit_mix='Demo',amenities='Demo')
        response=self.client.post(reverse('contract_associate',args=[doc.pk]),{'record':doc.record_id,'asset':asset.pk,'reason':'The source states Al Rayyana on page 1.'})
        self.assertEqual(response.status_code,302)
        doc.refresh_from_db();self.assertEqual(doc.record.asset_id,asset.pk)
        self.assertEqual(AssociationEvent.objects.count(),1)
        report=self.client.get(reverse('portfolio_report')+'?source=documents')
        self.assertContains(report,'AED 120,000')
        self.assertContains(report,reverse('contract_source',args=[doc.pk])+'#page=1')
        source=self.client.get(reverse('contract_source',args=[doc.pk]))
        self.assertEqual(source['Content-Type'],'application/pdf')
        self.assertEqual(source['X-Frame-Options'],'SAMEORIGIN')
        self.assertEqual(hashlib.sha256(b''.join(source.streaming_content)).hexdigest(),doc.sha256)
        field=run.fields.get(name='annual_rent')
        self.client.post(reverse('field_review',args=[field.pk]),{'decision':'confirmed'})
        field.refresh_from_db();self.assertEqual(field.reviewed_by,self.user)
        self.assertEqual(doc.record.data,{})

    def test_duplicate_upload_reuses_document_without_losing_association(self):
        doc=self.import_document()
        duplicate,created=ingest_pdf(self.pdf,'renamed.pdf',self.user,original_blob='renamed.pdf')
        self.assertFalse(created);self.assertEqual(duplicate.pk,doc.pk)
        self.assertEqual(ContractDocument.objects.count(),1)
        self.assertEqual(LeaseRecord.objects.count(),1)

    def test_malformed_pdf_and_missing_anonymization_confirmation(self):
        with self.assertRaises(contract_storage.DocumentError):ingest_pdf(b'not pdf','bad.pdf')
        response=self.client.post(reverse('contract_ingest'),{'files':SimpleUploadedFile('a.pdf',self.pdf)})
        self.assertEqual(response.status_code,302);self.assertFalse(ContractDocument.objects.exists())

    def test_model_fields_require_value_quote_page_and_allowed_name(self):
        pages=[{'page':1,'text':'Tenant Example. Rent: AED 120,000.'}]
        cases=[{'name':'annual_rent','value':'AED 900,000','page':1,'quote':'Rent: AED 120,000.'},
               {'name':'annual_rent','value':'AED 120,000','page':2,'quote':'Rent: AED 120,000.'},
               {'name':'annual_rent','value':'AED 120,000','page':True,'quote':'Rent: AED 120,000.'},
               {'name':{},'value':'AED 120,000','page':1,'quote':'Rent: AED 120,000.'},
               {'name':'annual_rent','value':'AED 120,000','page':1,'quote':'Fabricated AED 120,000.'}]
        for item in cases:
            fields,warnings=validate_fields({'fields':[item]},pages)
            self.assertEqual(fields,[]);self.assertTrue(warnings)

    def test_retries_keep_old_success_and_failed_provider_has_no_fake_values(self):
        doc=self.import_document();successful=self.extraction(doc)
        queued=queue_extraction(doc,self.user)
        self.assertEqual(queue_extraction(doc,self.user).pk,queued.pk)
        self.assertEqual(claim_run().pk,queued.pk);self.assertIsNone(claim_run())
        with patch('core.documents.extraction.extract_contract_fields',side_effect=contract_storage.DocumentError('EnginexAI unavailable')):process_run(queued)
        queued.refresh_from_db();self.assertEqual(queued.status,'failed');self.assertFalse(queued.fields.exists())
        self.assertEqual(record_rows([doc.record])[0]['evidence_count'],successful.fields.count())

    def test_reject_removes_fact_from_reports_but_retains_audit_record(self):
        doc=self.import_document();run=self.extraction(doc)
        field=run.fields.get(name='annual_rent')
        self.client.post(reverse('field_review',args=[field.pk]),{'decision':'rejected'})
        self.assertNotContains(self.client.get(reverse('portfolio_report')+'?source=documents'),'AED 120,000')
        self.assertTrue(ExtractedField.objects.filter(pk=field.pk).exists())

    def test_source_and_all_workspace_views_require_login(self):
        doc=self.import_document();self.client.logout()
        for url in [reverse('contracts'),reverse('portfolio_report'),reverse('record_detail',args=[doc.record_id]),reverse('contract_source',args=[doc.pk]),reverse('contract_status',args=[doc.pk])]:
            self.assertEqual(self.client.get(url).status_code,302)

    def test_source_integrity_failure_does_not_serve_changed_pdf(self):
        doc=self.import_document()
        from pathlib import Path
        (Path(self.directory.name)/doc.storage_key.split(':',1)[1]).write_bytes(b'%PDF-changed')
        self.assertEqual(self.client.get(reverse('contract_source',args=[doc.pk])).status_code,503)

    def test_manual_link_keeps_synthetic_baseline_and_enforces_record_location(self):
        call_command('populate_portfolio',records_per_location=10,verbosity=0)
        record=LeaseRecord.objects.filter(origin='synthetic').first()
        data=record.data.copy();doc=self.import_document();self.extraction(doc)
        other=Asset.objects.exclude(pk=record.asset_id).first()
        with self.assertRaises(contract_storage.DocumentError):associate(doc,record,other,'Deliberate demo association',self.user)
        with self.assertRaises(contract_storage.DocumentError):associate(doc,record,record.asset,'',self.user)
        associate(doc,record,record.asset,'Deliberate demo association for review',self.user)
        record.refresh_from_db();self.assertEqual(record.data,data)
        self.assertEqual(record_rows([record])[0]['evidence_count'],2)

    def test_csv_preserves_field_provenance_without_synthetic_source_links(self):
        LeaseRecord.objects.create(code='DEMO-CSV',origin='synthetic',data={'tenant_name':'=1+1','annual_rent':100})
        response=self.client.get(reverse('report_export'))
        rows=list(csv.DictReader(io.StringIO(response.content.decode())))
        self.assertEqual(rows[0]['value'],"'=1+1")
        self.assertTrue(all(row['provenance']=='Synthetic demo' and not row['pdf_url'] for row in rows))


class AdditivePortfolioTests(TestCase):
    def test_default_seed_is_large_deterministic_and_non_destructive(self):
        call_command('seed_demo',verbosity=0)
        asset=Asset.objects.get(name='Al Rayyana')
        metrics=PortfolioMetrics.objects.get(asset=asset)
        previous=(asset.units,metrics.in_place_rent)
        call_command('populate_portfolio',verbosity=0)
        self.assertEqual(LeaseRecord.objects.filter(origin='synthetic').count(),720)
        self.assertEqual(Asset.objects.count(),6)
        self.assertTrue(all(a.lease_records.count()==120 for a in Asset.objects.all()))
        record=LeaseRecord.objects.first();record.data['annual_rent']=98765;record.save()
        call_command('populate_portfolio',verbosity=0)
        self.assertEqual(LeaseRecord.objects.count(),720)
        record.refresh_from_db();self.assertEqual(record.data['annual_rent'],98765)
        asset.refresh_from_db();metrics.refresh_from_db()
        self.assertEqual((asset.units,metrics.in_place_rent),previous)

    def test_each_location_opens_its_own_dashboard_and_chat_scope(self):
        call_command('populate_portfolio',records_per_location=10,verbosity=0)
        user=get_user_model().objects.create_user(username='map-records-viewer')
        self.client.force_login(user)
        response=self.client.get(reverse('portfolio'))
        self.assertEqual(response.context['ready_count'],6)
        for location in response.context['locations']:
            dashboard=self.client.get(location['metrics_url'])
            self.assertEqual(dashboard.context['asset'].name,location['name'])
        with override_settings(**FOUNDRY_SETTINGS),patch('core.ai.legacy.foundry.get_answer',return_value='Gate demo') as answer:
            self.client.post(reverse('asset_chat',args=['gate']),data={'message':'What needs attention?'},content_type='application/json')
        self.assertEqual(answer.call_args.kwargs['context']['asset']['name'],'Gate')
