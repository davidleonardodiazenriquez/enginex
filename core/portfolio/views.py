
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static

from core.integrations import foundry
from core.feedback.selectors import property_feedback
from core.portfolio.context import get_dashboard_asset
from core.portfolio.locations import LOCATIONS, map_locations
from core.portfolio.scene import property_scene
from core.reports.selectors import portfolio_summary


@login_required
def portfolio_map(request):
    locations = map_locations()
    return render(request, "core/portfolio_map.html", {
        "locations": locations,
        "featured": locations[0],
        "ready_count": sum(location["ready"] for location in locations),
        "summary": portfolio_summary(),
    })


@login_required
def dashboard(request, asset_slug="al-rayyana"):
    location = next((item for item in LOCATIONS if item["id"]==asset_slug), None)
    if location is None:
        raise Http404
    asset = get_dashboard_asset(location["name"])
    tenant_total = 0
    vacancy_total = 0
    if asset:
        tenant_total = asset.tenant_revenues.aggregate(total=Sum("revenue_share"))["total"] or 0
        vacancy_total = asset.vacancies.aggregate(total=Sum("revenue_share"))["total"] or 0

    return render(
        request,
        "core/dashboard.html",
        {
            "asset": asset,
            "tenant_total": tenant_total,
            "vacancy_total": vacancy_total,
            "foundry_configured": foundry.is_configured(),
            "asset_slug": asset_slug,
            "asset_photo": static("core/locations/"+location["image"]),
            "property_scene": property_scene(asset, asset_slug) if asset else None,
            "summary": portfolio_summary(asset) if asset else None,
            "feedback_summary": property_feedback(asset) if asset else None,
            "asset_facts": [{"label":field.replace("_"," ").title(),"value":getattr(asset,field),"source":asset.field_sources.get(field,"Existing demo")} for field in ("name","location","asset_class","developer","buildings","units","unit_mix","amenities")] if asset else [],
        },
    )
