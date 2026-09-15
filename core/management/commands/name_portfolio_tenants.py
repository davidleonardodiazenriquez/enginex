"""Replace only generated tenant placeholders; preserve document evidence."""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import LeaseRecord, TenantRevenue
from core.portfolio.tenant_names import generated_tenant_name


PLACEHOLDER = re.compile(r"(?:Demo tenant|Tenant) (\d{2})-(\d{4,5})")
LEGACY_SUMMARY = re.compile(r"Tenant [A-J]")


class Command(BaseCommand):
    help = "Replace generated tenant placeholders with stable fictional names in English letters."

    @transaction.atomic
    def handle(self, *args, **options):
        renamed = {}
        records = []
        for record in LeaseRecord.objects.select_for_update().filter(origin="synthetic"):
            old_name = record.data.get("tenant_name", "")
            if not isinstance(old_name, str) or not PLACEHOLDER.fullmatch(old_name):
                continue
            name = generated_tenant_name(record.code)
            renamed[(record.asset_id, old_name)] = name
            record.data = {**record.data, "tenant_name": name}
            records.append(record)
        LeaseRecord.objects.bulk_update(records, ["data"])

        rankings = []
        for row in TenantRevenue.objects.select_for_update().select_related("asset"):
            match = PLACEHOLDER.fullmatch(row.tenant_name)
            if match:
                location, number = map(int, match.groups())
                row.tenant_name = renamed.get(
                    (row.asset_id, row.tenant_name),
                    generated_tenant_name(f"DEMO-{location:02d}-{number:05d}"),
                )
            elif row.asset.name == "Al Rayyana" and LEGACY_SUMMARY.fullmatch(row.tenant_name):
                row.tenant_name = generated_tenant_name(f"summary:{row.asset.name}:{row.rank}")
            else:
                continue
            rankings.append(row)
        TenantRevenue.objects.bulk_update(rankings, ["tenant_name"])
        self.stdout.write(self.style.SUCCESS(
            f"Named {len(records)} portfolio tenants and {len(rankings)} dashboard entries."
        ))
