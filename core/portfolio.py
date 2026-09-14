"""Read the dashboard asset and prepare its data for the assistant."""

from decimal import Decimal

from django.utils import timezone

from core.models import Asset


def get_dashboard_asset(name="Al Rayyana"):
    # Keep chat scoped to exactly the asset displayed by the dashboard.
    return (
        Asset.objects.select_related("metrics")
        .prefetch_related("tenant_revenues", "vacancies")
        .filter(name=name).first()
    )


def asset_context(asset):
    context = {
        "source": "Enginex dashboard database",
        "retrieved_at": timezone.now().isoformat(),
        "scope": "The single asset shown on the dashboard, not the entire portfolio",
        "data_status": "Hackathon sample data, not audited financial information",
        "units": {"monetary_values": "AED millions", "revenue_share": "percent"},
        "limitations": [
            "No reporting date, individual lease expiry dates, or tenant renewal status is stored.",
            "Ranked tenant and vacancy lists are revenue shares, not an occupancy rate.",
            "Stored percentages are rounded and may differ slightly from ratios of stored amounts.",
        ],
        "asset": None,
    }
    if asset is None:
        return context

    tenants = list(asset.tenant_revenues.all())
    vacancies = list(asset.vacancies.all())
    context["asset"] = {
        field: getattr(asset, field)
        for field in (
            "name", "location", "asset_class", "developer", "buildings", "units",
            "unit_mix", "amenities",
        )
    }
    context["tenant_revenue"] = {
        "rows": [
            {"rank": row.rank, "tenant": row.tenant_name, "revenue_share_pct": row.revenue_share}
            for row in tenants
        ],
        "listed_total_revenue_share_pct": sum((row.revenue_share for row in tenants), Decimal(0)),
    }
    context["vacancies"] = {
        "rows": [
            {"rank": row.rank, "unit": row.unit_name, "revenue_share_pct": row.revenue_share}
            for row in vacancies
        ],
        "listed_total_revenue_share_pct": sum((row.revenue_share for row in vacancies), Decimal(0)),
    }
    metrics = getattr(asset, "metrics", None)
    context["metrics"] = None
    if metrics is not None:
        context["metrics"] = {
            "due_renewals": {
                "completed_pct": metrics.due_completed_pct,
                "completed_aed_millions": metrics.due_completed_value,
                "incomplete_aed_millions": metrics.due_incomplete_value,
                "total_aed_millions": metrics.total_due,
            },
            "upcoming_renewals_to_year_end": {
                "signed_pct": metrics.upcoming_signed_pct,
                "signed_aed_millions": metrics.upcoming_signed_value,
                "unsigned_aed_millions": metrics.upcoming_unsigned_value,
                "total_aed_millions": metrics.total_upcoming,
            },
            "reversionary_potential": {
                "potential_pct": metrics.reversionary_pct,
                "in_place_rent_aed_millions": metrics.in_place_rent,
                "market_rent_aed_millions": metrics.market_rent,
                "potential_upside_aed_millions": metrics.potential_upside,
            },
        }
    from core.reporting import portfolio_summary, record_rows
    context["record_sample"] = portfolio_summary(asset)
    context["document_evidence"] = []
    records = asset.lease_records.filter(documents__isnull=False).distinct()[:20]
    for row in record_rows(records):
        context["document_evidence"].append({
            "record":row["record"].code,
            "association":"A user-selected portfolio association; the PDF is authoritative for its stated premises, not the association.",
            "fields":[{"name":field["name"],"baseline":field["baseline"],"baseline_source":field["baseline_source"],"evidence":field["evidence"]} for field in row["fields"]],
        })
    context["provenance_rules"] = "Legacy metrics are existing demo summaries. Record sample totals include only synthetic records. Document-backed values are separate, quoted from anonymized test PDFs, and may be unreviewed. Do not combine these populations, claim synthetic facts came from contracts, or treat manual map associations as documentary facts. Cite document title and page for document-backed answers."
    return context
