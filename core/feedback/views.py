from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from core.feedback.selectors import comparison_rows, feedback_summary, select_feedback
from core.feedback.taxonomy import SENTIMENTS, TOPICS
from core.models import Asset, ResidentFeedback


@login_required
def feedback_workspace(request):
    filters = {k: request.GET.get(k, "") for k in ("location", "sentiment", "group", "q", "start", "end", "topic", "theme_sentiment")}
    error = ""
    try:
        rows = select_feedback(filters)
    except ValueError as exc:
        rows, error = [], str(exc)
    summary = feedback_summary(rows)
    for sentiment in ("positive", "negative"):
        for topic in summary[sentiment + "_themes"]:
            topic["query"] = urlencode({**filters, "topic": topic["topic"], "theme_sentiment": sentiment})
    for keyword in summary["keywords"]:
        keyword["query"] = urlencode({**filters, "q": keyword["keyword"]})
    comparisons = comparison_rows(rows)
    for item in comparisons:
        item["query"] = urlencode({**filters, "location": item["location"]})
        item["nps_width"] = abs(item["nps"] or 0) / 2
    return render(request, "core/feedback.html", {
        "summary": summary, "comparisons": comparisons, "page_obj": Paginator(rows, 12).get_page(request.GET.get("page")),
        "filters": filters, "filter_query": urlencode(filters), "filter_error": error,
        "assets": Asset.objects.all(), "sentiments": SENTIMENTS, "topics": TOPICS,
    })


@login_required
def feedback_detail(request, pk):
    item = get_object_or_404(ResidentFeedback.objects.select_related("asset", "record"), pk=pk)
    return render(request, "core/feedback_detail.html", {"feedback": item})
