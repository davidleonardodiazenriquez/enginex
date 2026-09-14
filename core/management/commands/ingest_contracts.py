from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import contract_storage
from core.contracts import ingest_pdf, queue_extraction


class Command(BaseCommand):
    help = "Import explicitly selected local PDFs or storage blob names, without guessing map associations."

    def add_arguments(self, parser):
        parser.add_argument("--directory")
        parser.add_argument("--blob", action="append", default=[])
        parser.add_argument("--extract", action="store_true")

    def handle(self, *args, **options):
        if bool(options["directory"]) == bool(options["blob"]):
            raise CommandError("Use either --directory or one or more --blob names.")
        sources = []
        if options["directory"]:
            for path in sorted(Path(options["directory"]).glob("*.pdf")):
                sources.append((path.name, path, ""))
        else:
            sources = [(name, None, name) for name in options["blob"]]
        created = queued = 0
        for name, path, blob in sources:
            try:
                data = path.read_bytes() if path else contract_storage.read_blob(blob)
                doc, new = ingest_pdf(data, name, original_blob=blob)
                created += new
                if options["extract"] and not doc.runs.filter(status="completed").exists():
                    queue_extraction(doc)
                    queued += 1
                self.stdout.write(f"{'Imported' if new else 'Existing'}: {doc.title} · {doc.id}")
            except (contract_storage.DocumentError, OSError) as exc:
                raise CommandError(str(exc)) from None
        self.stdout.write(f"{len(sources)} documents checked; {created} imported; {queued} queued. No map associations inferred.")
