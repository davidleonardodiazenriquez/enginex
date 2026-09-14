from collections import defaultdict
from decimal import Decimal

from django.urls import reverse

from core.models import ContractDocument, ExtractedField, ExtractionRun, LeaseRecord
from core.record_fields import FIELDS, field_label


def evidence_for_records(records):
    documents = list(ContractDocument.objects.filter(record__in=records).select_related("record"))
    # A failed retry does not hide the last successful extraction. Older runs remain in history.
    run_ids = {}
    for run in ExtractionRun.objects.filter(document__in=documents, status="completed").order_by("-id"):
        run_ids.setdefault(run.document_id, run.id)
    evidence = defaultdict(lambda: defaultdict(list))
    for field in ExtractedField.objects.filter(run_id__in=run_ids.values()).exclude(review_status="rejected").select_related("run__document"):
        document = field.run.document
        evidence[document.record_id][field.name].append({
            "id": field.pk, "value": field.value, "page": field.page, "quote": field.quote,
            "review": field.get_review_status_display(), "status": field.review_status,
            "document_title": document.title, "document_id": str(document.pk),
            "source_label": document.source_label,
            "source_url": reverse("contract_source", args=[document.pk]) + f"#page={field.page}",
            "review_url": reverse("contract_detail", args=[document.pk]) + f"#field-{field.pk}",
        })
    return evidence


def record_rows(records, names=None):
    records = list(records)
    evidence = evidence_for_records(records)
    rows = []
    for record in records:
        fields = []
        selected = names if names is not None else FIELDS
        for name in selected:
            baseline = record.data.get(name)
            sources = evidence[record.pk].get(name, [])
            if names is None and baseline is None and not sources:
                continue
            fields.append({"name":name,"label":field_label(name),"baseline":baseline,
                           "baseline_source":"Synthetic demo" if record.origin=="synthetic" else "Manual record data",
                           "evidence":sources,"conflict":len({e["value"] for e in sources})>1})
        rows.append({"record":record,"fields":fields,"evidence_count":sum(len(v) for v in evidence[record.pk].values())})
    return rows


def portfolio_summary(asset=None):
    records = LeaseRecord.objects.all()
    if asset is not None:
        records = records.filter(asset=asset)
    synthetic = list(records.filter(origin="synthetic"))
    occupied = [r for r in synthetic if r.data.get("occupancy_status")=="Occupied"]
    annual = sum(Decimal(str(r.data.get("annual_rent",0))) for r in occupied)
    arrears = sum(Decimal(str(r.data.get("arrears",0))) for r in occupied)
    documents = ContractDocument.objects.filter(record__in=records)
    return {
        "records":records.count(),"synthetic_records":len(synthetic),"occupied":len(occupied),
        "occupancy_pct":round(len(occupied)/len(synthetic)*100,1) if synthetic else None,
        "annual_rent":annual,"arrears":arrears,"documents":documents.count(),
        "unassigned_documents":documents.filter(record__asset__isnull=True).count(),
        "as_of":min((r.as_of for r in synthetic if r.as_of),default=None),
        "synthetic_fields":sum(len(r.data) for r in synthetic),
        "scope":"Synthetic record sample only; not the full physical asset or legacy summary. Extracted values are excluded from these totals.",
    }
