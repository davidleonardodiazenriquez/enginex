"""Portfolio display names; stored values and document quotations stay unchanged."""

import re


def portfolio_text(value):
    if not isinstance(value, str):
        return value
    labels = {
        "Synthetic demo": "Portfolio record",
        "Existing demo": "Portfolio record",
        "existing demo": "Portfolio record",
        "Anonymized test contract": "Contract document",
        "demo": "Portfolio",
    }
    if value in labels:
        return labels[value]
    value = re.sub(r"\bDEMO-", "PR-", value)
    for before, after in (
        ("Demo tenant ", "Tenant "), ("Demo property owner", "Property owner"),
        (" (demo profile)", ""), ("Demo assumption; not assessed", "Not assessed"),
        ("Demo policy: ", ""), (" (demo assumption)", " (assumption)"),
    ):
        value = value.replace(before, after)
    return value


def stored_record_search(value):
    """Accept the displayed PR prefix as well as the original stored code."""
    return re.sub(r"\bPR-", "DEMO-", value, flags=re.IGNORECASE)


PRESENTATION_INSTRUCTIONS = """The presenter explains the demonstration data to the audience separately. In ordinary analysis, use 'portfolio records' for the synthetic population, 'summary metrics' for legacy metrics, and 'document evidence' for extracted facts. Do not repeat demo, synthetic, sample-data or anonymized-test disclaimers in routine replies or chart titles. Preserve meaningful scope, date, units, review status and missing-data limitations. Never claim generated values are verified, audited, or extracted from a PDF. If asked about authenticity or provenance, explain the synthetic data and anonymized test documents truthfully. Display stored DEMO- record/unit prefixes as PR-, 'Demo tenant' as 'Tenant', and 'Demo property owner' as 'Property owner'; original identifiers remain valid for tool queries. Keep document quotations verbatim."""
