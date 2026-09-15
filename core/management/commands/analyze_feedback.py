from django.core.management.base import BaseCommand

from core.feedback.analysis import analyze_feedback


class Command(BaseCommand):
    help = "Analyze resident feedback locally; reuse completed results for unchanged transcripts."

    def add_arguments(self, parser):
        parser.add_argument("--retry-failed", action="store_true")

    def handle(self, *args, **options):
        result = analyze_feedback(retry_failed=options["retry_failed"])
        self.stdout.write(f"Analyzed {result['completed']}; unchanged {result['skipped']}; failed {result['failed']}.")
