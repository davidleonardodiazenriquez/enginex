"""Ingestion, asynchronous extraction and explicit association of contract evidence."""

import hashlib
import logging
from pathlib import PurePosixPath

from django.db import transaction

from core.documents import storage as contract_storage
from core.integrations import foundry
from core.models import (
    AssociationEvent,
    ContractDocument,
    ExtractionRun,
    LeaseRecord,
)

logger = logging.getLogger(__name__)
EXTRACTION_LIMIT = 220_000


def ingest_pdf(data, filename, user=None, original_blob=""):
    page_count = contract_storage.inspect_pdf(data)
    digest = hashlib.sha256(data).hexdigest()
    existing = ContractDocument.objects.filter(sha256=digest).first()
    if existing:
        return existing, False
    key = contract_storage.store_pdf(data, digest)
    with transaction.atomic():
        record, _ = LeaseRecord.objects.get_or_create(code="DOC-" + digest[:20].upper(), defaults={"origin": "document"})
        document, created = ContractDocument.objects.get_or_create(sha256=digest, defaults={
            "title": PurePosixPath(filename.replace("\\", "/")).name[:240], "storage_key": key,
            "original_blob": original_blob, "size_bytes": len(data), "page_count": page_count,
            "record": record, "uploaded_by": user,
        })
    return document, created


@transaction.atomic
def queue_extraction(document, user=None):
    document = ContractDocument.objects.select_for_update().get(pk=document.pk)
    active = document.runs.filter(status__in=["queued", "running"]).first()
    if active:
        return active
    if not foundry.is_configured():
        raise contract_storage.DocumentError("Configure EnginexAI before starting extraction. Your PDF has been retained.")
    return ExtractionRun.objects.create(document=document, requested_by=user)


@transaction.atomic
def associate(document, record, asset, reason, user):
    if len(reason.strip()) < 8:
        raise contract_storage.DocumentError("Add a short reason explaining the association (at least 8 characters).")
    document = ContractDocument.objects.select_for_update().get(pk=document.pk)
    record = LeaseRecord.objects.select_for_update().get(pk=record.pk)
    if record.origin == "synthetic" and record.asset_id != (asset.pk if asset else None):
        raise contract_storage.DocumentError("The chosen record belongs to a different location. Choose its location or a different record.")
    if record.origin == "document":
        if record.asset_id != (asset.pk if asset else None) and record.documents.exclude(pk=document.pk).exists():
            raise contract_storage.DocumentError("This record has other documents. Reassign those individually before changing its location.")
        record.asset = asset
        record.save(update_fields=["asset"])
    AssociationEvent.objects.create(document=document, previous_record_code=document.record.code, record_code=record.code, location_name=asset.name if asset else "", reason=reason.strip(), user=user)
    document.record = record
    document.association_status = "manual" if asset else "outside"
    document.association_details = {"reason": reason.strip()}
    document.save(update_fields=["record", "association_status", "association_details"])
    return document
