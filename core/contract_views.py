import csv
import io
import subprocess

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from core import contract_storage
from core.contracts import associate, ingest_pdf, queue_extraction
from core.models import Asset, ContractDocument, ExtractedField, LeaseRecord
from core.record_fields import field_label
from core.reporting import portfolio_summary, record_rows


@login_required
def contracts_workspace(request):
    documents = ContractDocument.objects.select_related("record__asset").prefetch_related("runs")
    if request.GET.get("asset", "").isdigit():
        documents = documents.filter(record__asset_id=request.GET["asset"])
    if request.GET.get("q"):
        documents = documents.filter(title__icontains=request.GET["q"][:150])
    documents = list(documents)
    for doc in documents:
        doc.latest_run = next(iter(doc.runs.all()), None)
    blobs, next_marker, storage_error = [], None, ""
    if request.GET.get("browse"):
        try:
            blobs, next_marker = contract_storage.available_blobs(request.GET.get("marker"))
        except contract_storage.DocumentError as exc:
            storage_error = str(exc)
    return render(request,"core/contracts.html",{"documents":documents,"summary":portfolio_summary(),"blobs":blobs,"next_marker":next_marker,"storage_error":storage_error,"storage_configured":contract_storage.configured()})


@login_required
@require_POST
def contract_ingest(request):
    files, blob_names = request.FILES.getlist("files"), request.POST.getlist("blob")
    if not 1 <= len(files) + len(blob_names) <= 10:
        messages.error(request,"Select between 1 and 10 PDFs.")
        return redirect("contracts")
    if request.POST.get("acknowledge") != "yes":
        messages.error(request,"Confirm these PDFs are anonymized demo documents before importing.")
        return redirect("contracts")
    documents = []
    for item, blob_name in [(f,"") for f in files] + [(None,n) for n in blob_names]:
        try:
            if item and item.size > contract_storage.settings.CONTRACT_MAX_BYTES:
                raise contract_storage.DocumentError("Choose a PDF no larger than 25 MB.")
            data = item.read() if item else contract_storage.read_blob(blob_name)
            doc, created = ingest_pdf(data,item.name if item else blob_name,user=request.user,original_blob=blob_name)
            documents.append(doc)
            messages.success(request,f"{'Imported' if created else 'Already in workspace'}: {doc.title}.")
            if request.POST.get("extract") == "yes" and not doc.runs.filter(status="completed").exists():
                queue_extraction(doc,request.user)
        except contract_storage.DocumentError as exc:
            messages.error(request,str(exc))
    return redirect("contract_detail", pk=documents[0].pk) if len(documents)==1 else redirect("contracts")


@login_required
def contract_detail(request, pk):
    document = get_object_or_404(ContractDocument.objects.select_related("record__asset"),pk=pk)
    runs = list(document.runs.all())
    selected_run = next((run for run in runs if str(run.pk)==request.GET.get("run")), None)
    if not selected_run:
        selected_run = next((run for run in runs if run.status=="completed"), runs[0] if runs else None)
    fields = list(selected_run.fields.all()) if selected_run else []
    for field in fields:
        field.label = field_label(field.name)
    page = request.GET.get("page","1")
    page = max(1,min(int(page),document.page_count)) if page.isdigit() else 1
    suggestions = []
    if selected_run:
        locations = " ".join(field.value for field in fields if field.name=="property_location").casefold()
        suggestions = [asset for asset in Asset.objects.all() if asset.name.casefold() in locations]
    return render(request,"core/contract_detail.html",{
        "document":document,"runs":runs,"run":selected_run,"latest_run":runs[0] if runs else None,"fields":fields,
        "assets":Asset.objects.all(),"records":LeaseRecord.objects.select_related("asset"),"suggestions":suggestions,
        "page":page,"associations":document.associations.select_related("user"),
    })


@login_required
@require_POST
def contract_extract(request, pk):
    document = get_object_or_404(ContractDocument,pk=pk)
    try:
        queue_extraction(document,request.user)
        messages.success(request,"Extraction queued. The worker will read this PDF and send its numbered text pages to Astra.")
    except contract_storage.DocumentError as exc:
        messages.error(request,str(exc))
    return redirect("contract_detail",pk=pk)


@login_required
def contract_status(request,pk):
    document = get_object_or_404(ContractDocument,pk=pk)
    run = document.runs.first()
    return JsonResponse({"status":run.status if run else "uploaded","label":run.get_status_display() if run else "Uploaded"})


@login_required
@require_POST
def contract_associate(request,pk):
    document = get_object_or_404(ContractDocument,pk=pk)
    record_id, asset_id = request.POST.get("record",""), request.POST.get("asset","")
    if not record_id.isdigit() or (asset_id and not asset_id.isdigit()):
        messages.error(request,"Choose a valid record and location.")
        return redirect("contract_detail",pk=pk)
    record = get_object_or_404(LeaseRecord,pk=record_id)
    asset = get_object_or_404(Asset,pk=asset_id) if asset_id else None
    try:
        associate(document,record,asset,request.POST.get("reason","")[:2000],request.user)
        messages.success(request,"Association saved with your reason. Baseline values remain unchanged.")
    except contract_storage.DocumentError as exc:
        messages.error(request,str(exc))
    return redirect("contract_detail",pk=pk)


@login_required
@require_POST
def field_review(request,pk):
    field = get_object_or_404(ExtractedField.objects.select_related("run__document"),pk=pk)
    status = request.POST.get("decision")
    if status not in {"confirmed","rejected","pending"}:
        return HttpResponse("Invalid review decision",status=400)
    field.review_status, field.reviewed_by, field.reviewed_at = status,request.user,timezone.now()
    field.save(update_fields=["review_status","reviewed_by","reviewed_at"])
    return redirect(reverse("contract_detail",args=[field.run.document_id])+f"?run={field.run_id}#field-{field.pk}")


@login_required
@xframe_options_sameorigin
def contract_source(request,pk):
    document = get_object_or_404(ContractDocument,pk=pk)
    try:
        data = contract_storage.read_pdf(document)
    except contract_storage.DocumentError as exc:
        return HttpResponse(str(exc),status=503,content_type="text/plain")
    response = FileResponse(io.BytesIO(data),content_type="application/pdf",filename=document.title,as_attachment=False)
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def contract_page(request, pk, page):
    document = get_object_or_404(ContractDocument, pk=pk)
    if not 1 <= page <= document.page_count:
        return HttpResponse("Page not found", status=404)
    try:
        data = contract_storage.read_pdf(document)
        result = subprocess.run(
            ["pdftoppm", "-f", str(page), "-l", str(page), "-singlefile", "-scale-to", "1400", "-png", "-"],
            input=data, capture_output=True, timeout=30,
        )
        if result.returncode or not result.stdout.startswith(b"\x89PNG"):
            return HttpResponse("Page preview unavailable. Open the original PDF.", status=503)
    except (contract_storage.DocumentError, OSError, subprocess.TimeoutExpired):
        return HttpResponse("Page preview unavailable. Open the original PDF.", status=503)
    response = HttpResponse(result.stdout, content_type="image/png")
    response["Cache-Control"] = "private, max-age=3600"
    return response


def filtered_records(request):
    records = LeaseRecord.objects.select_related("asset")
    asset_id = request.GET.get("asset","")
    if asset_id == "unassigned":
        records = records.filter(asset__isnull=True)
    elif asset_id.isdigit():
        records = records.filter(asset_id=asset_id)
    if request.GET.get("source") == "synthetic":
        records = records.filter(origin="synthetic")
    elif request.GET.get("source") == "documents":
        records = records.filter(documents__isnull=False).distinct()
    query = request.GET.get("q","").strip()[:150]
    if query:
        records = records.filter(Q(code__icontains=query)|Q(data__tenant_name__icontains=query)|Q(data__unit_reference__icontains=query)|Q(documents__title__icontains=query)).distinct()
    return records


@login_required
def portfolio_report(request):
    records = filtered_records(request)
    page = Paginator(records,25).get_page(request.GET.get("page"))
    rows = record_rows(page.object_list,["tenant_name","unit_reference","annual_rent","lease_end"])
    params = request.GET.copy()
    params.pop("page",None)
    return render(request,"core/report.html",{"rows":rows,"page_obj":page,"summary":portfolio_summary(),"assets":Asset.objects.all(),"filter_query":params.urlencode()})


@login_required
def record_detail(request,pk):
    record = get_object_or_404(LeaseRecord.objects.select_related("asset"),pk=pk)
    return render(request,"core/record_detail.html",{"row":record_rows([record])[0],"record":record,"documents":record.documents.all()})


@login_required
def report_export(request):
    # One row per value: CSV retains competing evidence, origin, review state and source page.
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="enginex-field-provenance.csv"'
    writer = csv.writer(response)
    writer.writerow(["record","location","field","value","provenance","review","document","page","pdf_url","quote"])
    def safe(value):
        value = str(value) if value is not None else ""
        return "'"+value if value.startswith(("=","+","-","@","\t","\r")) else value
    for row in record_rows(filtered_records(request)):
        record = row["record"]
        prefix = [record.code, record.asset.name if record.asset else "Unassigned"]
        for field in row["fields"]:
            if field["baseline"] is not None:
                writer.writerow([safe(v) for v in prefix+[field["label"],field["baseline"],field["baseline_source"],"","","","",""]])
            for evidence in field["evidence"]:
                values = prefix + [field["label"], evidence["value"], "Document-backed · " + evidence["source_label"], evidence["review"], evidence["document_title"], evidence["page"], request.build_absolute_uri(evidence["source_url"]), evidence["quote"]]
                writer.writerow([safe(v) for v in values])
    return response
