"""Fast local, explainable transcript analysis; no provider or network calls."""

import hashlib
import re
from functools import lru_cache

from django.utils import timezone
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from core.feedback.taxonomy import TOPIC_PHRASES
from core.models import ResidentFeedback

VERSION = "local-vader-property-v3"


@lru_cache(maxsize=1)
def analyzer():
    engine = SentimentIntensityAnalyzer()
    # Domain vocabulary; security as a department is not itself positive sentiment.
    engine.lexicon.update({"security": 0, "questions": 0, "waste": 0, "contact": 0, "number": 0,
                          "unreliable": -2.5, "leaking": -1.5,
                          "dirty": -2.2, "neglected": -2.5, "broken": -2.5,
                          "tidy": 1.5, "efficiently": 1.7, "straightforward": 1.5,
                          "fixed": 2.5, "repaired": 2.5, "resolved": 2.5, "handled": 1.5,
                          "smoothly": 1.8, "patient": 1, "professional": 1.5, "quiet": 1.5})
    return engine


def polarity(value):
    return "positive" if value >= 0.05 else "negative" if value <= -0.05 else "neutral"


def sentence_score(sentence):
    # Score common service phrases in context; retain the untouched sentence as evidence.
    for pattern, replacement in (
        (r"\bno further questions\b", "all questions are answered"),
        (r"\black of clarity\b", "confusion"),
        (r"\b(?:takes|taking|took) too long\b", "frustrating delay"),
        (r"\bhad to circle\b", "had a frustrating wait"),
        (r"\bhave not helped\b", "have failed"),
        (r"\b(?:different|contradictory) (?:answers|instructions)\b", "conflicting instructions"),
        (r"\blarge puddles\b", "hazardous puddles"),
    ):
        sentence = re.sub(pattern, replacement, sentence, flags=re.I)
    return analyzer().polarity_scores(sentence)["compound"]


def resident_sentences(transcript):
    speakers = list(re.finditer(r"^(Agent|Resident)(?: \([^\n]*?\))?:\s*", transcript, re.I | re.M))
    if speakers:
        blocks = [transcript[match.end():speakers[i + 1].start() if i + 1 < len(speakers) else len(transcript)].strip()
                  for i, match in enumerate(speakers) if match.group(1).lower() == "resident"]
    else:
        blocks = [transcript.strip()]
    return [s.strip() for block in blocks for s in re.split(r"(?<=[.!?])\s+", block)
            if s.strip() and not re.search(r"recommendation score is \d+ out of 10", s, re.I)]


def phrase_in(phrase, text):
    return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I))


def analyze_text(transcript):
    sentences = resident_sentences(transcript)
    if not sentences:
        raise ValueError("No resident comments were found to analyze.")
    themes, keywords, scored = [], set(), []
    for sentence in sentences:
        matches = {topic: [p for p in phrases if phrase_in(p, sentence)] for topic, phrases in TOPIC_PHRASES.items()}
        matches = {topic: phrases for topic, phrases in matches.items() if phrases}
        if not matches:
            continue
        score = sentence_score(sentence)
        scored.append((sentence, score))
        for topic, phrases in matches.items():
            themes.append({"topic": topic, "sentiment": polarity(score), "quote": sentence})
            keywords.update(p for p in phrases if not any(p != other and p in other for other in phrases))
    # Analyze free-form comments even when no known property theme is mentioned.
    if not scored:
        scored = [(s, sentence_score(s)) for s in sentences]
    value = round(sum(score for _, score in scored) / len(scored), 4)
    return {"sentiment": polarity(value), "sentiment_score": value,
            "summary": " ".join(s for s, _ in scored[:2]), "themes": themes, "keywords": sorted(keywords)}


def analyze_feedback(*, retry_failed=False):
    completed = skipped = failed = 0
    for item in ResidentFeedback.objects.order_by("pk").iterator(chunk_size=100):
        digest = hashlib.sha256(item.transcript.encode()).hexdigest()
        if item.analysis_status == "completed" and item.analysis_input_hash == digest and item.analysis_version == VERSION:
            skipped += 1
            continue
        if item.analysis_status == "failed" and not retry_failed:
            skipped += 1
            continue
        try:
            result = analyze_text(item.transcript)
            # Do not attach stale analysis if a transcript was edited while being read.
            changed = ResidentFeedback.objects.filter(pk=item.pk, transcript=item.transcript).update(
                **result, analysis_status="completed", analysis_model="VADER 3.3.2 + property vocabulary",
                analysis_version=VERSION, analysis_input_hash=digest, analyzed_at=timezone.now(), analysis_error="",
            )
            completed += changed
        except ValueError as exc:
            ResidentFeedback.objects.filter(pk=item.pk, transcript=item.transcript).update(
                analysis_status="failed", analysis_error=str(exc)[:240],
                sentiment="", sentiment_score=None, summary="", keywords=[], themes=[], analyzed_at=None,
            )
            failed += 1
    return {"completed": completed, "skipped": skipped, "failed": failed}
