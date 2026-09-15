import time
from concurrent.futures import ThreadPoolExecutor

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from core.documents.extraction import claim_run, process_run


class Command(BaseCommand):
    help = "Process durable contract extraction jobs; --loop runs the Container App worker."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")

    def handle(self, *args, **options):
        def process(run):
            close_old_connections()
            try:
                process_run(run)
            finally:
                close_old_connections()

        # One coordinator claims jobs transactionally; two bounded workers call EnginexAI.
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = set()
            while True:
                close_old_connections()
                for future in list(pending):
                    if future.done():
                        future.result()
                        pending.remove(future)
                run = claim_run() if len(pending) < 2 else None
                if run:
                    pending.add(pool.submit(process, run))
                    continue
                if not options["loop"] and not pending:
                    return
                time.sleep(3)
