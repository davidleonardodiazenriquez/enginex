"""Read-only portfolio tools. All chart numbers are calculated from stored records."""

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import Max, Q
from django.urls import reverse
from django.utils import timezone

from core.models import Asset, ContractDocument, ExtractedField, ExtractionRun, LeaseRecord
from core.portfolio import asset_context
from core.record_fields import FIELDS
from core.reporting import portfolio_summary

NUMERIC_FIELDS = {"bedrooms", "floor", "area_sqm", "annual_rent", "market_rent", "security_deposit", "payment_count", "arrears", "service_charge", "parking_spaces"}
DATE_FIELDS = {"lease_start", "lease_end"}


class QueryError(ValueError):
    pass


def text(value, limit=150):
    if not isinstance(value, str) or len(value) > limit:
        raise QueryError("Use a short text value.")
    return value.strip()


def number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            return None
        return result
    except (InvalidOperation, ValueError, TypeError):
        return None


def location_filter(query, location, relation="asset"):
    location = text(location or "all")
    if location.lower() in {"all", "entire portfolio", ""}:
        return query
    if location.lower() in {"unassigned", "outside map"}:
        return query.filter(**{relation + "__isnull": True})
    asset = Asset.objects.filter(name__iexact=location).first()
    if not asset:
        raise QueryError("Unknown location. Use an asset name from the portfolio overview, all, or unassigned.")
    return query.filter(**{relation: asset})


def overview():
    assets = []
    for asset in Asset.objects.select_related("metrics").prefetch_related("tenant_revenues", "vacancies"):
        context = asset_context(asset)
        assets.append({"asset": context["asset"], "field_sources": asset.field_sources,
                       "synthetic_sample": context["record_sample"], "legacy_metrics_aed_millions": context["metrics"],
                       "tenant_rankings": context["tenant_revenue"], "vacancy_rankings": context["vacancies"]})
    return {"source": "Live application database", "retrieved_at": timezone.now().isoformat(),
            "scope": "All portfolio assets and unassigned documents", "summary": portfolio_summary(),
            "assets": assets, "evidence_fields": evidence_query().count(),
            "available_record_fields": FIELDS, "numeric_fields": sorted(NUMERIC_FIELDS),
            "limits": "Synthetic record amounts are AED. Legacy metrics are AED millions. No historical occupancy time series. Document values are verbatim and not added to synthetic totals. Query record details or contract evidence with the tools."}


def selected_records(args):
    query = location_filter(LeaseRecord.objects.select_related("asset").order_by("code"), args.get("location", "all"))
    origin = args.get("origin", "synthetic")
    if origin not in {"synthetic", "document", "all"}:
        raise QueryError("Origin must be synthetic, document, or all.")
    if origin != "all":
        query = query.filter(origin=origin)
    search = text(args.get("search", ""))
    if search:
        query = query.filter(Q(code__icontains=search) | Q(data__tenant_name__icontains=search) | Q(data__unit_reference__icontains=search))
    filters = args.get("filters", [])
    if not isinstance(filters, list) or len(filters) > 8:
        raise QueryError("Use at most eight field filters.")
    for item in filters:
        if not isinstance(item, dict) or item.get("field") not in FIELDS or item.get("op") not in {"eq", "contains", "gt", "gte", "lt", "lte"}:
            raise QueryError("Choose an available field and comparison operator.")
        value = item.get("value")
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise QueryError("Filter values must be text or numbers.")
        if item["op"] in {"gt", "gte", "lt", "lte"} and item["field"] not in NUMERIC_FIELDS | DATE_FIELDS:
            raise QueryError("Range comparisons require numeric or date fields.")
        if item["field"] in NUMERIC_FIELDS and item["op"] != "contains" and number(value) is None:
            raise QueryError("This filter requires a finite number.")
        if item["field"] in DATE_FIELDS and item["op"] in {"gt", "gte", "lt", "lte"}:
            try:
                date.fromisoformat(str(value))
            except ValueError:
                raise QueryError("Use ISO dates: YYYY-MM-DD.") from None

    def matches(row):
        for item in filters:
            actual, expected, op = row.data.get(item["field"]), item["value"], item["op"]
            if actual is None:
                return False
            if op == "contains":
                ok = str(expected).casefold() in str(actual).casefold()
            elif item["field"] in NUMERIC_FIELDS:
                a, b = number(actual), number(expected)
                ok = a is not None and b is not None and compare(a, b, op)
            elif item["field"] in DATE_FIELDS and op != "eq":
                try:
                    ok = compare(date.fromisoformat(str(actual)), date.fromisoformat(str(expected)), op)
                except ValueError:
                    ok = False
            else:
                ok = compare(str(actual).casefold(), str(expected).casefold(), op)
            if not ok:
                return False
        return True
    # Aggregate every matching row; pagination is applied only to detail results.
    return [row for row in query.iterator(chunk_size=500) if matches(row)]


def compare(a, b, op):
    return {"eq": lambda: a == b, "gt": lambda: a > b, "gte": lambda: a >= b, "lt": lambda: a < b, "lte": lambda: a <= b}[op]()


def page_args(args, maximum=50):
    offset, limit = args.get("offset", 0), args.get("limit", min(25, maximum))
    if type(offset) is not int or not 0 <= offset <= 100000 or type(limit) is not int or not 1 <= limit <= maximum:
        raise QueryError(f"Use offset >= 0 and limit 1–{maximum}.")
    return offset, limit


def query_records(args):
    rows = selected_records(args)
    fields = args.get("fields", ["tenant_name", "unit_reference", "annual_rent", "lease_end", "occupancy_status", "arrears"])
    if not isinstance(fields, list) or not 1 <= len(fields) <= 15 or any(not isinstance(f, str) or f not in FIELDS for f in fields):
        raise QueryError("Choose 1–15 available record fields.")
    sort = args.get("sort_by", "code")
    if sort not in FIELDS and sort != "code":
        raise QueryError("Unknown sort field.")
    descending = args.get("descending", False)
    if type(descending) is not bool:
        raise QueryError("descending must be true or false.")
    rows.sort(key=lambda r: (number(r.data.get(sort)) or Decimal(0)) if sort in NUMERIC_FIELDS else str(r.code if sort == "code" else r.data.get(sort, "")), reverse=descending)
    offset, limit = page_args(args)
    result = [{"code": r.code, "location": r.asset.name if r.asset else "Unassigned", "origin": r.origin,
               "as_of": r.as_of, "values": {f: r.data.get(f) for f in fields}, "record_url": reverse("record_detail", args=[r.pk])} for r in rows[offset:offset + limit]]
    return {"total_matching": len(rows), "returned": len(result), "offset": offset, "next_offset": offset + limit if offset + limit < len(rows) else None,
            "rows": result, "provenance": "Baseline values only; synthetic rows are generated demo data. Use contract_evidence for document-derived facts."}


def aggregate_records(args):
    if args.get("origin", "synthetic") != "synthetic":
        raise QueryError("Financial/chart aggregation uses synthetic records only. Query contract_evidence for verbatim extracted values.")
    rows = selected_records({**args, "origin": "synthetic"})
    group_by, metric = args.get("group_by", "location"), args.get("metric", "count")
    metric_field = args.get("metric_field", "annual_rent")
    if group_by not in {"location", "all", "lease_end_month", "lease_start_month"} | set(FIELDS):
        raise QueryError("Unknown grouping field.")
    if metric not in {"count", "sum", "average", "occupancy"} or metric_field not in NUMERIC_FIELDS:
        raise QueryError("Use count, sum, average or occupancy, with a supported numeric field.")
    groups = defaultdict(list)
    for row in rows:
        if group_by == "location":
            label = row.asset.name if row.asset else "Unassigned"
        elif group_by == "all":
            label = "All matching records"
        elif group_by.endswith("_month"):
            value = row.data.get(group_by[:-6])
            try:
                label = date.fromisoformat(str(value)).strftime("%Y-%m")
            except ValueError:
                label = "Not stated"
        else:
            label = str(row.data.get(group_by, "Not stated"))
        groups[label].append(row)
    values = []
    for label, members in groups.items():
        numbers = [number(r.data.get(metric_field)) for r in members]
        numbers = [value for value in numbers if value is not None]
        if metric == "count":
            value = len(members)
        elif metric == "occupancy":
            value = round(sum(r.data.get("occupancy_status") == "Occupied" for r in members) / len(members) * 100, 2)
        elif not numbers:
            value = None
        else:
            total = sum(numbers, Decimal(0))
            value = float(total if metric == "sum" else total / len(numbers))
        values.append({"label": label, "value": value, "records": len(members)})
    sort = args.get("sort", "label")
    if sort not in {"label", "highest", "lowest"}:
        raise QueryError("Sort by label, highest or lowest.")
    values.sort(key=lambda r: r["label"] if sort == "label" else (r["value"] if r["value"] is not None else float('-inf')), reverse=sort == "highest")
    offset, limit = page_args(args, maximum=60)
    shown = values[offset:offset + limit]
    unit = "%" if metric == "occupancy" else "records" if metric == "count" else "AED" if metric_field in {"annual_rent", "market_rent", "arrears", "security_deposit", "service_charge"} else "sqm" if metric_field == "area_sqm" else metric_field
    chart_type = args.get("chart_type", "none")
    if chart_type not in {"none", "bar", "line", "doughnut"}:
        raise QueryError("Charts support bar, line or doughnut.")
    if chart_type == "doughnut" and (len(shown) > 12 or any(r["value"] is None or r["value"] < 0 for r in shown) or metric not in {"count", "sum"}):
        raise QueryError("Doughnut charts need up to 12 non-negative count/sum groups. Use a bar chart for rates or averages.")
    result = {"rows": shown, "matched_records": len(rows), "total_groups": len(values), "offset": offset,
              "next_offset": offset + limit if offset + limit < len(values) else None, "metric": metric, "metric_field": metric_field,
              "unit": unit, "group_by": group_by, "filters": args.get("filters", []), "location": args.get("location", "all"),
              "as_of": min((r.as_of for r in rows if r.as_of), default=None), "provenance": "Synthetic demo records only; contract facts and legacy metrics excluded."}
    if chart_type != "none":
        result["chart"] = {"type": chart_type, "title": text(args.get("title", f"{metric.title()} by {group_by.replace('_', ' ')}"), 120),
                           "rows": shown, "unit": unit, "provenance": result["provenance"], "matched_records": len(rows),
                           "as_of": result["as_of"], "total_groups": len(values), "group_by": group_by, "metric": metric,
                           "metric_field": metric_field, "location": result["location"], "filters": result["filters"]}
    return result


def evidence_query():
    latest = ExtractionRun.objects.filter(status="completed").values("document_id").annotate(latest=Max("id")).values_list("latest", flat=True)
    return ExtractedField.objects.filter(run_id__in=latest).exclude(review_status="rejected").select_related("run__document__record__asset").order_by("run__document__title", "name", "page", "pk")


def contract_evidence(args):
    query = location_filter(evidence_query(), args.get("location", "all"), "run__document__record__asset")
    fields = args.get("fields", [])
    if not isinstance(fields, list) or len(fields) > 15 or any(not isinstance(f, str) or f not in FIELDS for f in fields):
        raise QueryError("Use available field names.")
    if fields:
        query = query.filter(name__in=fields)
    search, title = text(args.get("search", "")), text(args.get("document", ""))
    if search:
        query = query.filter(Q(value__icontains=search) | Q(quote__icontains=search) | Q(run__document__title__icontains=search))
    if title:
        query = query.filter(run__document__title__icontains=title)
    offset, limit = page_args(args)
    total = query.count()
    rows = []
    for field in query[offset:offset + limit]:
        doc = field.run.document
        rows.append({"document": doc.title, "document_id": str(doc.pk), "field": field.name, "value": field.value,
                     "quote": field.quote, "page": field.page, "review": field.get_review_status_display(),
                     "record": doc.record.code, "associated_location": doc.record.asset.name if doc.record.asset else "Unassigned",
                     "source_label": doc.source_label, "source_url": reverse("contract_source", args=[doc.pk]) + f"#page={field.page}"})
    return {"rows": rows, "total_matching": total, "offset": offset, "next_offset": offset + limit if offset + limit < total else None,
            "provenance": "Latest successful extraction; rejected values excluded. These are anonymized test PDFs. A manual map association does not establish the stated premises."}


def document_pages(args):
    title, search = text(args.get("document", "")), text(args.get("search", ""))
    page_number = args.get("page", 0)
    if type(page_number) is not int or not 0 <= page_number <= 80:
        raise QueryError("Use PDF page 1–80, or zero to search pages.")
    docs = location_filter(ContractDocument.objects.select_related("record__asset"), args.get("location", "all"), "record__asset")
    if title:
        docs = docs.filter(title__icontains=title)
    offset, limit = page_args(args, maximum=12)
    matches = []
    for doc in docs.order_by("title"):
        run = doc.runs.filter(status="completed").first()
        if not run:
            continue
        for page in run.pages:
            if page_number and page["page"] != page_number:
                continue
            source_text = page.get("text", "")
            position = source_text.casefold().find(search.casefold()) if search else 0
            if position < 0:
                continue
            start = max(0, position - 400)
            excerpt = source_text[start:start + 7000]
            matches.append({"document": doc.title, "page": page["page"], "text": excerpt, "text_truncated": len(source_text) > len(excerpt),
                            "source_url": reverse("contract_source", args=[doc.pk]) + f"#page={page['page']}", "provenance": doc.source_label})
    return {"rows": matches[offset:offset + limit], "total_matching_pages": len(matches),
            "next_offset": offset + limit if offset + limit < len(matches) else None,
            "limitation": "Stored PDF text layer only. Image-only content and OCR errors require visual source review."}


def document_library(args):
    docs = location_filter(ContractDocument.objects.select_related("record__asset"), args.get("location", "all"), "record__asset")
    search = text(args.get("search", ""))
    if search:
        docs = docs.filter(title__icontains=search)
    offset, limit = page_args(args)
    rows = []
    for doc in docs.order_by("title")[offset:offset + limit]:
        latest, successful = doc.runs.first(), doc.runs.filter(status="completed").first()
        rows.append({"document": doc.title, "document_id": str(doc.pk), "pages": doc.page_count, "record": doc.record.code,
                     "location": doc.record.asset.name if doc.record.asset else "Unassigned", "source_label": doc.source_label,
                     "latest_status": latest.status if latest else "uploaded", "evidence_fields": successful.fields.exclude(review_status="rejected").count() if successful else 0,
                     "warnings": successful.warnings if successful else [],
                     "associations": list(doc.associations.values("record_code", "location_name", "reason", "created_at")[:5]),
                     "document_url": reverse("contract_detail", args=[doc.pk]), "source_url": reverse("contract_source", args=[doc.pk])})
    return {"rows": rows, "total_matching": docs.count(), "next_offset": offset + limit if offset + limit < docs.count() else None}
