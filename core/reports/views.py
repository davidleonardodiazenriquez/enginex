import csv

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from core.models import Asset, LeaseRecord
from core.presentation import stored_record_search
from core.reports.selectors import portfolio_summary, record_rows


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
        matches = Q()
        for term in {query, stored_record_search(query)}:
            matches |= Q(code__icontains=term)|Q(data__tenant_name__icontains=term)|Q(data__unit_reference__icontains=term)|Q(documents__title__icontains=term)
        records = records.filter(matches).distinct()
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
