import json
import logging
from urllib import error, parse, request as urllib_request

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core.models import Asset

logger = logging.getLogger(__name__)


def health(request):
    return JsonResponse({"status": "healthy"})


def _foundry_configured() -> bool:
    endpoint = settings.AZURE_AI_FOUNDRY_ENDPOINT
    return bool(
        endpoint
        and settings.AZURE_AI_FOUNDRY_API_KEY
        and (settings.AZURE_AI_FOUNDRY_DEPLOYMENT or "/chat/completions" in endpoint)
    )


@login_required
def dashboard(request):
    asset = (
        Asset.objects.select_related("metrics")
        .prefetch_related("tenant_revenues", "vacancies")
        .first()
    )
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
            "foundry_configured": _foundry_configured(),
        },
    )


def _foundry_url() -> str:
    endpoint = settings.AZURE_AI_FOUNDRY_ENDPOINT.rstrip("/")
    if "/chat/completions" in endpoint:
        separator = "&" if "?" in endpoint else "?"
        if "api-version=" not in endpoint:
            endpoint = (
                f"{endpoint}{separator}api-version={settings.AZURE_AI_FOUNDRY_API_VERSION}"
            )
        return endpoint
    deployment = parse.quote(settings.AZURE_AI_FOUNDRY_DEPLOYMENT, safe="")
    return (
        f"{endpoint}/openai/deployments/{deployment}/chat/completions"
        f"?api-version={settings.AZURE_AI_FOUNDRY_API_VERSION}"
    )


@require_POST
@login_required
def chat(request):
    if not _foundry_configured():
        return JsonResponse({"error": "Azure AI Foundry is not configured."}, status=503)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON request."}, status=400)

    message = str(body.get("message", "")).strip()
    if not message:
        return JsonResponse({"error": "A message is required."}, status=400)
    if len(message) > 4000:
        return JsonResponse({"error": "Message exceeds 4,000 characters."}, status=400)

    request_payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an asset management copilot. Give concise, decision-oriented "
                    "answers about portfolio performance. Clearly label assumptions and do "
                    "not present sample dashboard data as audited financial information."
                ),
            },
            {"role": "user", "content": message},
        ],
        "temperature": 0.2,
        "max_tokens": 700,
    }
    if (
        settings.AZURE_AI_FOUNDRY_DEPLOYMENT
        and "/chat/completions" in settings.AZURE_AI_FOUNDRY_ENDPOINT
    ):
        request_payload["model"] = settings.AZURE_AI_FOUNDRY_DEPLOYMENT
    payload = json.dumps(request_payload).encode("utf-8")
    foundry_request = urllib_request.Request(
        _foundry_url(),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "api-key": settings.AZURE_AI_FOUNDRY_API_KEY,
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(foundry_request, timeout=45) as response:
            result = json.loads(response.read())
        answer = result["choices"][0]["message"]["content"]
        return JsonResponse({"answer": answer})
    except (error.HTTPError, error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("Azure AI Foundry request failed: %s", type(exc).__name__)
        return JsonResponse({"error": "The AI assistant is temporarily unavailable."}, status=502)
