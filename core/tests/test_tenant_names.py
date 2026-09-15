import io

from django.core.management import call_command
from django.test import TestCase

from core.models import LeaseRecord, TenantRevenue


class PortfolioTenantNameTests(TestCase):
    def test_rename_is_scoped_consistent_and_repeatable(self):
        call_command("populate_portfolio", records_per_location=10, stdout=io.StringIO())
        record = LeaseRecord.objects.first()
        original = {**record.data, "tenant_name": "Demo tenant 01-0001"}
        record.data = original
        record.save()
        ranking = TenantRevenue.objects.filter(asset=record.asset).first()
        ranking.tenant_name = original["tenant_name"]
        ranking.save()
        share = ranking.revenue_share
        preserved = [
            LeaseRecord.objects.create(code="CUSTOM", origin="synthetic", data={"tenant_name": "Jane Parker"}),
            LeaseRecord.objects.create(code="EMPTY", origin="synthetic", data={"tenant_name": "Vacant"}),
            LeaseRecord.objects.create(code="DOC-ONE", origin="document", data={"tenant_name": "Demo tenant 01-0001"}),
        ]
        before = {row.pk: row.data for row in preserved}

        call_command("name_portfolio_tenants", stdout=io.StringIO())
        record.refresh_from_db()
        ranking.refresh_from_db()
        name = record.data["tenant_name"]
        self.assertRegex(name, r"^[A-Za-z]+(?: [A-Za-z]+)+$")
        self.assertEqual(record.data, {**original, "tenant_name": name})
        self.assertEqual(ranking.tenant_name, name)
        self.assertEqual(ranking.revenue_share, share)
        self.assertEqual(dict(LeaseRecord.objects.filter(pk__in=before).values_list("pk", "data")), before)
        output = io.StringIO()
        call_command("name_portfolio_tenants", stdout=output)
        self.assertIn("Named 0 portfolio tenants and 0 dashboard entries", output.getvalue())

    def test_new_population_and_legacy_rankings_use_person_names(self):
        call_command("seed_demo", stdout=io.StringIO())
        ranking = TenantRevenue.objects.get(rank=1)
        seeded_name = ranking.tenant_name
        ranking.tenant_name = "Tenant A"
        ranking.save()
        call_command("name_portfolio_tenants", stdout=io.StringIO())
        ranking.refresh_from_db()
        self.assertEqual(ranking.tenant_name, seeded_name)

        call_command("populate_portfolio", records_per_location=12, stdout=io.StringIO())
        for record in LeaseRecord.objects.all():
            if record.data["occupancy_status"] == "Vacant":
                self.assertEqual(record.data["tenant_name"], "Vacant")
            else:
                self.assertRegex(record.data["tenant_name"], r"^[A-Za-z]+(?: [A-Za-z]+)+$")
        self.assertFalse(TenantRevenue.objects.filter(tenant_name__startswith="Tenant ").exists())
