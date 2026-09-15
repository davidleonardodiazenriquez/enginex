import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST

from core.integrations import foundry
from core.portfolio.context import asset_context, get_dashboard_asset
from core.portfolio.locations import LOCATIONS


@require_POST
@login_required
def chat(request, asset_slug="al-rayyana"):
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
        location = next((item for item in LOCATIONS if item["id"]==asset_slug), None)
        if location is None:
            raise Http404
        answer = foundry.get_answer(
            message, context=asset_context(get_dashboard_asset(location["name"])), history=history,
        )
        return JsonResponse({"answer": answer})
    except foundry.FoundryUnavailable:
        return JsonResponse({"error": "The AI assistant is temporarily unavailable."}, status=502)
