from collections import Counter

from django.core.management.base import BaseCommand

from core.documents.association import resolve_document_location
from core.models import ContractDocument


class Command(BaseCommand):
    help = "Resolve locations from existing extraction evidence without reprocessing PDFs. Manual decisions are preserved."

    def handle(self, *args, **options):
        counts = Counter()
        for document_id in ContractDocument.objects.values_list("pk", flat=True).iterator():
            counts[resolve_document_location(document_id)] += 1
        self.stdout.write(", ".join(f"{status}: {count}" for status, count in sorted(counts.items())))
