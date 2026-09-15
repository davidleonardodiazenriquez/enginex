from django.core.management.base import BaseCommand
from django.db import transaction

from core.feedback.generation import populate_feedback


class Command(BaseCommand):
    help = "Add 50 fictional resident transcripts per property, preserving existing feedback."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(f"Added {populate_feedback()} resident transcripts."))
