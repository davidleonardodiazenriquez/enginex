"""One calculation path for property KPIs, the feedback report and AI tools."""

from collections import Counter, defaultdict
from datetime import date

from django.db.models import Q
from django.urls import reverse

from core.feedback.taxonomy import SENTIMENTS, TOPICS
from core.models import Asset, ResidentFeedback


def short_text(value, maximum=150):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("Use a short text filter.")
    return value.strip()


def select_feedback(args):
    query = ResidentFeedback.objects.select_related("asset", "record")
    location = short_text(args.get("location", "all") or "all")
    if location != "all":
        asset = Asset.objects.filter(name__iexact=location).first()
        if not asset:
            raise ValueError("Choose a location from the portfolio.")
        query = query.filter(asset=asset)
    dates = {}
    for key in ("start", "end"):
        value = short_text(args.get(key, ""))
        if value:
            try:
                dates[key] = date.fromisoformat(value)
            except ValueError:
                raise ValueError("Use dates in YYYY-MM-DD format.") from None
            query = query.filter(**{"received_on__gte" if key == "start" else "received_on__lte": dates[key]})
    if len(dates) == 2 and dates["start"] > dates["end"]:
        raise ValueError("The start date must be on or before the end date.")
    sentiment = short_text(args.get("sentiment", ""))
    if sentiment:
        if sentiment not in SENTIMENTS:
            raise ValueError("Choose positive, neutral or negative sentiment.")
        query = query.filter(analysis_status="completed", sentiment=sentiment)
    group = short_text(args.get("group", ""))
    groups = {"promoter": Q(recommendation_score__gte=9), "passive": Q(recommendation_score__in=[7, 8]),
              "detractor": Q(recommendation_score__lte=6), "unscored": Q(recommendation_score__isnull=True)}
    if group:
        if group not in groups:
            raise ValueError("Choose promoter, passive, detractor or unscored.")
        query = query.filter(groups[group])
    search = short_text(args.get("q", ""))
    if search:
        query = query.filter(Q(transcript__icontains=search) | Q(resident_name__icontains=search) | Q(reference__icontains=search))
    topic = short_text(args.get("topic", ""))
    theme_sentiment = short_text(args.get("theme_sentiment", ""))
    if topic and topic not in TOPICS:
        raise ValueError("Choose a supported feedback theme.")
    if theme_sentiment and theme_sentiment not in SENTIMENTS:
        raise ValueError("Choose positive, neutral or negative theme sentiment.")
    rows = list(query)
    if topic or theme_sentiment:
        rows = [r for r in rows if r.analysis_status == "completed" and any(
            (not topic or t["topic"] == topic) and (not theme_sentiment or t["sentiment"] == theme_sentiment)
            for t in r.themes
        )]
    return rows


def feedback_summary(rows):
    rows = list(rows)
    scored = [r for r in rows if r.recommendation_score is not None]
    groups = Counter(r.nps_group.lower() for r in scored)
    total = len(scored)
    nps = round(100 * (groups["promoter"] - groups["detractor"]) / total, 1) if total else None
    analyzed = [r for r in rows if r.analysis_status == "completed"]
    sentiments = Counter(r.sentiment for r in analyzed)
    keywords = Counter(k for r in analyzed for k in set(r.keywords))
    themes = Counter(pair for r in analyzed for pair in {(t["topic"], t["sentiment"]) for t in r.themes})
    dates = [r.received_on for r in rows]
    return {
        "responses": len(rows), "scored": total, "unscored": len(rows) - total,
        "nps": nps, "nps_display": f"{nps:+g}" if nps is not None else "—",
        "promoters": groups["promoter"], "passives": groups["passive"], "detractors": groups["detractor"],
        "promoter_pct": round(groups["promoter"] / total * 100, 1) if total else 0,
        "passive_pct": round(groups["passive"] / total * 100, 1) if total else 0,
        "detractor_pct": round(groups["detractor"] / total * 100, 1) if total else 0,
        "analyzed": len(analyzed), "pending": len(rows) - len(analyzed),
        "positive": sentiments["positive"], "neutral": sentiments["neutral"], "negative": sentiments["negative"],
        "positive_pct": round(sentiments["positive"] / len(analyzed) * 100, 1) if analyzed else None,
        "period_start": min(dates) if dates else None, "period_end": max(dates) if dates else None,
        "keywords": [{"keyword": k, "count": n} for k, n in keywords.most_common(18)],
        "positive_themes": [{"topic": t, "count": n} for (t, s), n in themes.most_common() if s == "positive"],
        "negative_themes": [{"topic": t, "count": n} for (t, s), n in themes.most_common() if s == "negative"],
    }


def property_feedback(asset):
    return feedback_summary(ResidentFeedback.objects.filter(asset=asset))


def comparison_rows(rows):
    groups = defaultdict(list)
    for item in rows:
        groups[item.asset.name].append(item)
    return [{"location": name, **feedback_summary(items)} for name, items in sorted(groups.items())]


def transcript_data(item):
    return {"reference": item.reference, "resident": item.resident_name, "location": item.asset.name,
            "received_on": item.received_on, "recommendation_score": item.recommendation_score,
            "nps_group": item.nps_group, "analysis_status": item.analysis_status, "sentiment": item.sentiment,
            "summary": item.summary, "themes": item.themes, "keywords": item.keywords,
            "transcript": item.transcript, "source_url": reverse("feedback_detail", args=[item.pk]),
            "code": item.reference, "source_label": "Resident feedback", "origin": item.origin,
            "analysis_method": item.analysis_model, "analysis_version": item.analysis_version}
