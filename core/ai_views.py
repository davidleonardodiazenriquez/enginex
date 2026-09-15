import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from core import analyst, foundry
from core.models import Asset
from core.reporting import portfolio_summary


@login_required
def workspace(request):
    return render(request, "core/enginex_ai.html", {"summary": portfolio_summary(), "ai_assets": Asset.objects.all()})


@require_POST
@login_required
def chat(request):
    try:
        body = json.loads(request.body)
        if not isinstance(body, dict) or not isinstance(body.get("message"), str) or not 1 <= len(body["message"].strip()) <= 4000:
            raise ValueError
        history = body.get("history", [])
        if not isinstance(history, list) or len(history) > 8 or len(history) % 2:
            raise ValueError
        for index, turn in enumerate(history):
            if not isinstance(turn, dict) or turn.get("role") != ("user" if index % 2 == 0 else "assistant") or not isinstance(turn.get("content"), str) or not 1 <= len(turn["content"].strip()) <= 6000:
                raise ValueError
        location = body.get("current_location")
        if location is not None and (not isinstance(location, str) or not Asset.objects.filter(name=location).exists()):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Send a question up to 4,000 characters and a valid conversation history."}, status=400)
    if not foundry.is_configured():
        return JsonResponse({"error": "EnginexAI is not configured. Your portfolio remains available in the reports."}, status=503)
    try:
        result = analyst.answer(body["message"].strip(), [{"role": t["role"], "content": t["content"]} for t in history], location)
    except foundry.FoundryUnavailable:
        return JsonResponse({"error": "EnginexAI could not complete this analysis. Try a narrower question or retry. No records were changed."}, status=502)
    return JsonResponse(result)
