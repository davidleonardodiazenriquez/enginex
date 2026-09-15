import io
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from core.ai.queries import QueryError
from core.feedback.analysis import analyze_feedback, analyze_text
from core.feedback.queries import feedback_insights, query_feedback
from core.feedback.selectors import feedback_summary, select_feedback
from core.models import Asset, LeaseRecord, ResidentFeedback


class FeedbackTests(TestCase):
    def setUp(self):
        self.asset = Asset.objects.create(name="Gate", buildings=3, units=100)

    def item(self, score=9, **kwargs):
        defaults = {"asset": self.asset, "resident_name": "Omar Hassan", "received_on": date(2026, 9, 1),
                    "transcript": "Resident: The swimming pool is excellent.", "recommendation_score": score}
        return ResidentFeedback.objects.create(reference=f"TEST-{ResidentFeedback.objects.count()}", **(defaults | kwargs))

    def test_nps_boundaries_include_passives_and_exclude_missing_scores(self):
        for score in (0, 6, 7, 8, 9, 10, None):
            self.item(score)
        result = feedback_summary(ResidentFeedback.objects.all())
        self.assertEqual((result["nps"], result["scored"], result["unscored"]), (0, 6, 1))
        self.assertEqual((result["promoters"], result["passives"], result["detractors"]), (2, 2, 2))
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.item(11)

    def test_global_score_uses_response_counts_not_average_property_nps(self):
        other = Asset.objects.create(name="Arc", buildings=1, units=20)
        for _ in range(3):
            self.item(10)
        self.item(0, asset=other)
        self.assertEqual(feedback_insights({})["summary"]["nps"], 50)
        self.assertEqual(feedback_insights({"location": "Arc"})["summary"]["nps"], -100)

    def test_empty_selection_has_no_score(self):
        result = feedback_summary([])
        self.assertIsNone(result["nps"])
        self.assertIsNone(result["positive_pct"])
        self.assertEqual(result["nps_display"], "—")

    def test_sentiment_ignores_agent_and_recommendation_score(self):
        transcript = "Agent: Excellent, wonderful, amazing!\nResident: The gym equipment is broken and I am disappointed.\nAgent: What is your score?\nResident: My recommendation score is 10 out of 10."
        first = self.item(10, transcript=transcript)
        second = self.item(0, transcript=transcript.replace("10 out of 10", "0 out of 10"))
        with patch("urllib.request.urlopen", side_effect=AssertionError("Local analysis must not call a provider")):
            self.assertEqual(analyze_feedback()["completed"], 2)
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(first.sentiment, "negative")
        self.assertEqual(first.sentiment_score, second.sentiment_score)
        self.assertEqual(first.nps_group, "Promoter")
        self.assertTrue(all(t["quote"] in first.transcript for t in first.themes))

    def test_local_language_handles_neutral_negation_and_resolved_issues(self):
        cases = {
            "The gym is excellent and I love it.": "positive",
            "The gym is not good and the broken equipment is disappointing.": "negative",
            "I use the recycling point beside the waste collection area once a week.": "neutral",
            "The maintenance team arrived on time and fixed the leaking tap on the first visit.": "positive",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(analyze_text(text)["sentiment"], expected)

    def test_analysis_reuses_unchanged_results_and_reprocesses_edited_text(self):
        item = self.item()
        analyze_feedback()
        self.assertEqual(analyze_feedback(), {"completed": 0, "skipped": 1, "failed": 0})
        item.transcript = "The gym is broken and the experience has been terrible."
        item.save(update_fields=["transcript"])
        self.assertEqual(analyze_feedback()["completed"], 1)
        item.refresh_from_db()
        self.assertEqual(item.sentiment, "negative")

    def test_theme_and_keyword_counts_are_distinct_transcripts(self):
        self.item(transcript="The swimming pool is excellent. The swimming pool is wonderful.")
        self.item(transcript="The swimming pool is dirty and disappointing.")
        analyze_feedback()
        result = feedback_insights({"group_by": "keywords", "metric": "count"})
        self.assertEqual(next(r["value"] for r in result["rows"] if r["label"] == "swimming pool"), 2)
        result = feedback_insights({"group_by": "positive_themes", "metric": "count"})
        self.assertEqual(result["rows"], [{"label": "Facilities", "value": 1, "records": 1}])
        rows = query_feedback({"topic": "Facilities", "theme_sentiment": "negative"})
        self.assertEqual(rows["total_matching"], 1)
        self.assertIn("disappointing", rows["rows"][0]["transcript"])

    def test_filters_dates_pagination_and_safe_chart_types(self):
        self.item(0, received_on=date(2026, 8, 1))
        latest = self.item(10)
        self.assertEqual(select_feedback({"start": "2026-09-01", "end": "2026-09-01"}), [latest])
        self.assertEqual(query_feedback({"limit": 1})["next_offset"], 1)
        self.assertEqual(feedback_insights({"chart_type": "bar"})["chart"]["unit"], "NPS points")
        for args in ({"start": "bad"}, {"location": "Missing"}, {"limit": 21}, {"offset": -1}):
            with self.subTest(args=args), self.assertRaises(QueryError):
                query_feedback(args)
        with self.assertRaises(QueryError):
            feedback_insights({"chart_type": "doughnut"})

    def test_views_require_login_and_source_links_open_the_transcript(self):
        item = self.item()
        for url in (reverse("feedback"), reverse("feedback_detail", args=[item.pk])):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(get_user_model().objects.create_user(username="feedback-viewer"))
        analyze_feedback()
        page = self.client.get(reverse("feedback"))
        self.assertContains(page, "+100")
        self.assertContains(page, reverse("feedback_detail", args=[item.pk]))
        self.assertContains(self.client.get(reverse("feedback_detail", args=[item.pk])), item.transcript)
        self.assertContains(self.client.get(reverse("feedback") + "?start=wrong"), "Use dates in YYYY-MM-DD format.")

    def test_population_adds_fifty_per_property_and_preserves_existing_data(self):
        call_command("populate_portfolio", records_per_location=60, stdout=io.StringIO())
        before = list(LeaseRecord.objects.values_list("pk", "data"))
        call_command("populate_feedback", stdout=io.StringIO())
        self.assertEqual(ResidentFeedback.objects.count(), 300)
        self.assertTrue(all(a.resident_feedback.count() == 50 for a in Asset.objects.all()))
        item = ResidentFeedback.objects.first()
        item.transcript = "My own edited resident comment."
        item.save()
        call_command("populate_feedback", stdout=io.StringIO())
        item.refresh_from_db()
        self.assertEqual(item.transcript, "My own edited resident comment.")
        self.assertEqual(list(LeaseRecord.objects.values_list("pk", "data")), before)
        self.assertEqual(ResidentFeedback.objects.count(), 300)
