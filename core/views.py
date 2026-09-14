import json

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core import foundry
from core.portfolio import asset_context, get_dashboard_asset


def health(request):
    return JsonResponse({"status": "healthy"})


@login_required
def dashboard(request):
    asset = get_dashboard_asset()
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
        },
    )


@require_POST
@login_required
def chat(request):
    if not foundry.is_configured():
        return JsonResponse({"error": "Azure AI Foundry is not configured."}, status=503)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON request."}, status=400)

    if not isinstance(body, dict) or not isinstance(body.get("message"), str):
        return JsonResponse({"error": "A text message is required."}, status=400)
    message = body["message"].strip()
    if not message:
        return JsonResponse({"error": "A message is required."}, status=400)
    if len(message) > 4000:
        return JsonResponse({"error": "Message exceeds 4,000 characters."}, status=400)

    history = body.get("history", [])
    if not isinstance(history, list) or len(history) > 6 or len(history) % 2:
        return JsonResponse({"error": "Invalid conversation history."}, status=400)
    for index, turn in enumerate(history):
        expected_role = "user" if index % 2 == 0 else "assistant"
        if (
            not isinstance(turn, dict)
            or turn.get("role") != expected_role
            or not isinstance(turn.get("content"), str)
            or not 1 <= len(turn["content"].strip()) <= 4000
        ):
            return JsonResponse({"error": "Invalid conversation history."}, status=400)
    # Only role/content are forwarded; clients cannot supply model instructions
    # or replace the authoritative database snapshot.
    history = [{"role": turn["role"], "content": turn["content"].strip()} for turn in history]

    try:
        answer = foundry.get_answer(
            message, context=asset_context(get_dashboard_asset()), history=history,
        )
        return JsonResponse({"answer": answer})
    except foundry.FoundryUnavailable:
        return JsonResponse({"error": "The AI assistant is temporarily unavailable."}, status=502)
