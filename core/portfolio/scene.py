"""Read synthetic unit-code groups for an illustrative, location-specific model."""

import re
from decimal import Decimal
from urllib.parse import urlencode

from django.urls import reverse


def property_scene(asset, slug):
    groups = {f"B{number:02d}": [] for number in range(1, 7)}
    for record in asset.lease_records.filter(origin="synthetic").only("data"):
        match = re.fullmatch(r"DEMO-\d{2}-(B\d{2})-U\d+", str(record.data.get("unit_reference", "")))
        if match and match[1] in groups:
            groups[match[1]].append(record.data)

    zones = []
    for code, rows in groups.items():
        occupied = [row for row in rows if row.get("occupancy_status") == "Occupied"]
        zones.append({
            "code": code,
            "records": len(rows),
            "occupied": len(occupied),
            "occupancy": round(len(occupied) / len(rows) * 100, 1) if rows else None,
            "annual_rent": str(sum((Decimal(str(row.get("annual_rent", 0))) for row in occupied), Decimal(0))),
            "report_url": reverse("portfolio_report") + "?" + urlencode({"asset": asset.pk, "source": "synthetic", "q": f"-{code}-"}),
        })
    return {"slug": slug, "name": asset.name, "zones": zones}
