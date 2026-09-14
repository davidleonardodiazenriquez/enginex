"""Shared field names for the demo, evidence review, reports and extraction."""

FIELDS = {
    "tenant_name": "Tenant", "landlord": "Landlord", "unit_reference": "Unit reference",
    "property_location": "Premises / location", "lease_reference": "Lease reference",
    "unit_type": "Unit type", "bedrooms": "Bedrooms", "floor": "Floor", "area_sqm": "Area (sqm)",
    "lease_start": "Lease start / effective date", "lease_end": "Lease end", "term": "Lease term",
    "annual_rent": "Annual / first-year rent (AED)", "market_rent": "Indicative market rent (AED)",
    "currency": "Currency", "security_deposit": "Security deposit (AED)",
    "payment_frequency": "Payment frequency", "payment_count": "Payments per year",
    "occupancy_status": "Occupancy status", "renewal_status": "Renewal status",
    "arrears": "Outstanding rent (AED)", "service_charge": "Service / FM charge (AED)",
    "parking_spaces": "Parking spaces", "permitted_use": "Permitted use",
    "notice_period": "Notice period", "escalation": "Rent review / escalation",
    "vat": "VAT treatment", "late_payment": "Late payment terms",
    "break_clause": "Break / termination clause", "fit_out": "Fit-out / improvement contribution",
    "furnished": "Furnished", "maintenance_status": "Maintenance status", "risk_band": "Demo risk band",
}


def field_label(name):
    return FIELDS.get(name, name.replace("_", " ").title())
