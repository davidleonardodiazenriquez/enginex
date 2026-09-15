import os
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Asset, PortfolioMetrics, TenantRevenue, Vacancy
from core.portfolio.tenant_names import generated_tenant_name


class Command(BaseCommand):
    help = "Create or refresh the Enginex sample portfolio and optional demo user."

    @transaction.atomic
    def handle(self, *args, **options):
        asset, _ = Asset.objects.update_or_create(
            name="Al Rayyana",
            defaults={
                "location": "Khalifa City A, Abu Dhabi",
                "asset_class": "Residential Apartments",
                "developer": "Aldar",
                "buildings": 33,
                "units": 1537,
                "unit_mix": "1–3 Bedroom Apartments",
                "amenities": "Pools, gym, squash courts, retail plaza, landscaped gardens",
            },
        )

        tenants = [
            (generated_tenant_name(f"summary:{asset.name}:{rank}"), share)
            for rank, share in enumerate(
                ["12.4", "9.8", "7.6", "6.1", "5.4", "4.7", "4.2", "3.3", "2.9", "2.1"], 1
            )
        ]
        vacancies = [
            ("Retail Unit 12", "2.1"), ("Retail Unit 27", "1.6"),
            ("Retail Unit 08", "1.3"), ("Retail Unit 31", "1.1"),
            ("Retail Unit 04", "0.9"), ("Retail Unit 19", "0.7"),
            ("Retail Unit 14", "0.6"), ("Retail Unit 02", "0.5"),
            ("Retail Unit 15", "0.4"), ("Retail Unit 30", "0.4"),
        ]

        asset.tenant_revenues.all().delete()
        TenantRevenue.objects.bulk_create(
            [TenantRevenue(asset=asset, rank=rank, tenant_name=name, revenue_share=Decimal(value))
             for rank, (name, value) in enumerate(tenants, start=1)]
        )
        asset.vacancies.all().delete()
        Vacancy.objects.bulk_create(
            [Vacancy(asset=asset, rank=rank, unit_name=name, revenue_share=Decimal(value))
             for rank, (name, value) in enumerate(vacancies, start=1)]
        )
        PortfolioMetrics.objects.update_or_create(
            asset=asset,
            defaults={
                "due_completed_pct": Decimal("94"),
                "due_completed_value": Decimal("1294"),
                "due_incomplete_value": Decimal("83"),
                "upcoming_signed_pct": Decimal("68"),
                "upcoming_signed_value": Decimal("212"),
                "upcoming_unsigned_value": Decimal("100"),
                "reversionary_pct": Decimal("8.2"),
                "in_place_rent": Decimal("1387"),
                "market_rent": Decimal("1501"),
            },
        )

        username = os.getenv("DEMO_USERNAME", "").strip()
        password = os.getenv("DEMO_PASSWORD", "")
        if username and password:
            user_model = get_user_model()
            user, _ = user_model.objects.get_or_create(username=username)
            user.is_staff = False
            user.is_superuser = False
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Demo user '{username}' is ready."))

        self.stdout.write(self.style.SUCCESS("Sample portfolio data is ready."))
