"""Read-only, bounded feedback tools for EnginexAI; calculations stay in Python."""

from core.feedback.selectors import comparison_rows, feedback_summary, select_feedback, transcript_data
from core.feedback.taxonomy import SENTIMENTS


def selected(args):
    from core.ai.queries import QueryError
    try:
        return select_feedback({**args, "q": args.get("search", "")})
    except ValueError as exc:
        raise QueryError(str(exc)) from None


def query_feedback(args):
    from core.ai.queries import page_args
    rows = selected(args)
    offset, limit = page_args(args, maximum=20)
    return {"rows": [transcript_data(r) for r in rows[offset:offset + limit]],
            "total_matching": len(rows), "next_offset": offset + limit if offset + limit < len(rows) else None,
            "provenance": "Generated resident interviews. Quotes are actual stored transcript text. Local VADER sentiment is a heuristic, not a human-reviewed finding."}


def feedback_insights(args):
    from core.ai.queries import QueryError, text
    items = selected(args)
    summary = feedback_summary(items)
    group = args.get("group_by", "location")
    metric = args.get("metric", "nps")
    if group not in {"location", "sentiment", "positive_themes", "negative_themes", "keywords"}:
        raise QueryError("Group feedback by location, sentiment, positive_themes, negative_themes or keywords.")
    if metric not in {"nps", "count"} or metric == "nps" and group != "location":
        raise QueryError("NPS comparisons use location groups. For themes, keywords and sentiment use count.")
    comparisons = comparison_rows(items)
    if group == "location":
        rows = [{"label": r["location"], "value": r["nps"] if metric == "nps" else r["responses"], "responses": r["responses"],
                 "scored": r["scored"], "promoters": r["promoters"], "passives": r["passives"], "detractors": r["detractors"]} for r in comparisons]
    elif group == "sentiment":
        rows = [{"label": s.title(), "value": summary[s]} for s in SENTIMENTS]
    else:
        key = "keyword" if group == "keywords" else "topic"
        rows = [{"label": r[key], "value": r["count"]} for r in summary[group]]
    kind = args.get("chart_type", "none")
    for row in rows:
        row["records"] = row.get("scored", row["value"]) if metric == "nps" else row.get("responses", row["value"])
    if kind not in {"none", "bar", "line", "doughnut"} or kind == "doughnut" and (metric == "nps" or group in {"positive_themes", "negative_themes", "keywords"}):
        raise QueryError("Use a bar chart for NPS or overlapping themes/keywords. Doughnuts support response counts by location or sentiment.")
    result = {"rows": rows, "matched_records": len(items), "summary": summary, "comparisons": comparisons,
              "nps_formula": "100 × (promoters − detractors) / scored responses. Promoters 9–10; passives 7–8; detractors 0–6. Unscored responses excluded.",
              "count_basis": "Themes and keywords count distinct transcripts mentioning each item; a transcript may mention multiple items. Sentiment counts use analyzed transcripts only.",
              "provenance": "Generated resident interviews; local VADER + property vocabulary. NPS uses explicit recommendation scores, never inferred sentiment."}
    if kind != "none":
        result["chart"] = {"type": kind, "title": text(args.get("title", "Resident NPS by property" if metric == "nps" else "Resident feedback"), 120),
                           "rows": rows, "unit": "NPS points" if metric == "nps" else "transcripts", "group_by": group, "metric": metric,
                           "metric_field": "recommendation_score" if metric == "nps" else "transcripts", "location": args.get("location", "all"),
                           "total_groups": len(rows), "matched_records": len(items), "as_of": summary["period_end"],
                           "record_label": "responses" if metric == "nps" else "transcripts",
                           "display_source": f"Resident feedback · {summary['scored']} scored responses · {summary['analyzed']} analyzed transcripts · {summary['period_start']} to {summary['period_end']}",
                           "provenance": result["provenance"],
                           "filters": {k: v for k, v in args.items() if k in {"start", "end", "sentiment", "group", "topic", "theme_sentiment", "search"} and v}}
    return result
