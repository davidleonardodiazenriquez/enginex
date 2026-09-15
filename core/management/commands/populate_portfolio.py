"""Repeatable, additive demo data. Never deletes or updates existing business rows."""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Asset, LeaseRecord, PortfolioMetrics, TenantRevenue, Vacancy
from core.portfolio.locations import LOCATIONS
from core.portfolio.tenant_names import generated_tenant_name

AS_OF = date(2026, 9, 14)


class Command(BaseCommand):
    help = "Add 120 synthetic unit/lease records per map location, preserving existing records."

    def add_arguments(self, parser):
        parser.add_argument("--records-per-location", type=int, default=120)

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["records_per_location"]
        if not 10 <= count <= 1000:
            raise CommandError("Choose 10–1,000 records per location.")
        created_count = 0
        profiles = [(33,1537,100000),(3,2200,125000),(1,990,110000),(3,636,98000),(125,1240,170000),(5,320,185000)]
        for index, (location, (buildings, homes, base_rent)) in enumerate(zip(LOCATIONS, profiles), 1):
            defaults = {
                "location": location["area"] + ", Abu Dhabi", "asset_class": location["category"],
                "developer": "Aldar", "buildings": buildings, "units": homes,
                "unit_mix": "1–3 bedroom apartments" if index != 5 else "3–5 bedroom villas",
                "amenities": "Pool, gym, parking and community facilities (demo profile)",
                "field_sources": {name: "Synthetic demo" for name in ["buildings","units","unit_mix","amenities","developer"]} | {name: "Map catalog" for name in ["name","location","asset_class"]},
            }
            asset, _ = Asset.objects.get_or_create(name=location["name"], defaults=defaults)
            for number in range(1, count + 1):
                code = f"DEMO-{index:02d}-{number:05d}"
                rng = random.Random(index * 10000 + number)
                occupied = number % 11 != 0
                bedrooms = rng.choice([1,2,2,3]) if index != 5 else rng.choice([3,4,5])
                annual = int(base_rent * (0.65 + bedrooms * 0.2) * rng.uniform(0.88,1.12) / 500) * 500
                start = AS_OF - timedelta(days=rng.randint(10, 700))
                end = start + timedelta(days=365 if (AS_OF-start).days < 355 else 730)
                renewal = "Signed" if number % 4 else "In discussion"
                data = {
                    "tenant_name": generated_tenant_name(code) if occupied else "Vacant",
                    "landlord": "Demo property owner", "unit_reference": f"DEMO-{index:02d}-B{(number-1)//20+1:02d}-U{number:03d}",
                    "property_location": location["name"], "lease_reference": f"SYN-{index:02d}-{number:05d}" if occupied else "Not applicable",
                    "unit_type": "Villa" if index == 5 else "Apartment", "bedrooms": bedrooms,
                    "floor": 0 if index == 5 else rng.randint(1,30), "area_sqm": bedrooms * 48 + rng.randint(12,40),
                    "lease_start": start.isoformat() if occupied else "Not applicable",
                    "lease_end": end.isoformat() if occupied else "Not applicable", "term": "12 months" if (end-start).days==365 else "24 months",
                    "annual_rent": annual if occupied else 0, "market_rent": int(annual * rng.uniform(1.025,1.14) / 500) * 500,
                    "currency": "AED", "security_deposit": int(annual * .05) if occupied else 0,
                    "payment_frequency": "Quarterly", "payment_count": 4, "occupancy_status": "Occupied" if occupied else "Vacant",
                    "renewal_status": renewal if occupied else "Not applicable", "arrears": int(annual / 12) if occupied and number % 13 == 0 else 0,
                    "service_charge": rng.randint(2500,5500), "parking_spaces": min(bedrooms,2), "permitted_use": "Residential",
                    "notice_period": "90 days", "escalation": "Subject to renewal negotiation", "vat": "Demo assumption; not assessed",
                    "late_payment": "Demo policy: follow-up after 7 days", "break_clause": "Two months' rent (demo assumption)",
                    "fit_out": "Not applicable", "furnished": "Yes" if number % 5 == 0 else "No",
                    "maintenance_status": "Work order open" if number % 17 == 0 else "Clear",
                    "risk_band": "High" if number % 13 == 0 else ("Medium" if number % 4 == 0 else "Low"),
                }
                _, created = LeaseRecord.objects.get_or_create(code=code, defaults={"asset":asset,"origin":"synthetic","data":data,"as_of":AS_OF})
                created_count += created
            rows = list(asset.lease_records.filter(origin="synthetic"))
            occupied_rows = [r for r in rows if r.data.get("occupancy_status") == "Occupied"]
            rent = sum(Decimal(str(r.data["annual_rent"])) for r in occupied_rows)
            market = sum(Decimal(str(r.data["market_rent"])) for r in occupied_rows)
            million = Decimal("1000000")
            defaults_metrics = {
                "due_completed_pct": Decimal("80"), "due_completed_value": rent * Decimal(".16") / million,
                "due_incomplete_value": rent * Decimal(".04") / million, "upcoming_signed_pct": Decimal("65"),
                "upcoming_signed_value": rent * Decimal(".26") / million, "upcoming_unsigned_value": rent * Decimal(".14") / million,
                "reversionary_pct": (market-rent)/rent*100 if rent else 0,
                "in_place_rent": rent/million,"market_rent":market/million,
            }
            PortfolioMetrics.objects.get_or_create(asset=asset, defaults=defaults_metrics)
            for rank, record in enumerate(sorted(occupied_rows, key=lambda r:r.data["annual_rent"], reverse=True)[:10],1):
                TenantRevenue.objects.get_or_create(asset=asset,rank=rank,defaults={"tenant_name":record.data["tenant_name"],"revenue_share":Decimal(str(record.data["annual_rent"]))/rent*100 if rent else 0})
            total_market = sum(Decimal(str(r.data["market_rent"])) for r in rows)
            for rank, record in enumerate([r for r in rows if r.data.get("occupancy_status")=="Vacant"][:10],1):
                Vacancy.objects.get_or_create(asset=asset,rank=rank,defaults={"unit_name":record.data["unit_reference"],"revenue_share":Decimal(str(record.data["market_rent"]))/total_market*100 if total_market else 0})
        self.stdout.write(self.style.SUCCESS(f"Added {created_count} synthetic records. Existing records and user accounts preserved. As of {AS_OF}."))
