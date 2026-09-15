"""Resolve contract locations from cited premises, preserving human decisions."""

import re
import unicodedata

from django.db import transaction

from core.models import Asset, AssociationEvent, ContractDocument, LeaseRecord

# Only explicit names/phase aliases; ambiguous district or building names need review.
ALIASES = {
    "gate": ("gate towers", "gate tower"),
    "arc": ("the arc", "arc towers", "arc tower"),
    "the bridges ii": ("the bridges 2", "bridges ii", "bridges 2"),
}
UNCERTAIN = re.compile(r"\b(not|near|nearby|opposite|adjacent|formerly|previously|excluding|except)\b|\b(close to|instead of|registered office|correspondence address|landlord address|tenant address)\b")


def normalized(value):
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", str(value)).casefold()))


def contains(text, phrase):
    return f" {phrase} " in f" {text} "


def evaluate_location(run, assets):
    """Return an explainable result without changing any record."""
    result = {"run_id": run.pk if run else None, "candidate_ids": [], "evidence": []}
    if not run:
        return {**result, "status": "pending", "reason": "Extract the contract to identify its premises."}
    fields = list(run.fields.filter(name="property_location").exclude(review_status="rejected"))
    if not fields:
        return {**result, "status": "review", "reason": "No usable premises location was extracted. Choose the location from the PDF."}
    pages = {page["page"]: normalized(page["text"]) for page in run.pages}
    values, matches, unclear = [], set(), False
    for field in fields:
        value, quote = normalized(field.value), normalized(field.quote)
        if not value or not quote or field.page not in pages or not contains(quote, value) or not contains(pages[field.page], quote):
            return {**result, "status": "review", "reason": "A premises value could not be verified against its cited page. Review the PDF."}
        result["evidence"].append({"field_id": field.pk, "run_id": run.pk, "page": field.page,
                                   "value": field.value, "quote": field.quote})
        found = set()
        for asset in assets:
            name = normalized(asset.name)
            # Short names can describe ordinary features (an entrance gate or an arc).
            names = ALIASES.get(name, ()) + (() if name in {"gate", "arc"} else (name,))
            if value == name or any(contains(value, alias) for alias in names):
                found.add(asset.pk)
        matches.update(found)
        values.append((value, found))
        unclear = unclear or bool(UNCERTAIN.search(value) or UNCERTAIN.search(quote))
        if re.search(r"\b(landlord|lessor|tenant|lessee)\b", quote) and not re.search(r"\b(premises|property|location|project|building|unit|demise)\b", quote):
            unclear = True
    result["candidate_ids"] = sorted(matches)
    if len(matches) > 1:
        return {**result, "status": "review", "reason": "The premises evidence names more than one portfolio location. Choose the correct association."}
    if not matches:
        return {**result, "status": "review", "reason": "The stated premises do not clearly match a location in this portfolio. Choose a location or mark the contract outside the portfolio."}
    matched_values = [value for value, found in values if found]
    conflicting = any(not found and not any(contains(matched, value) for matched in matched_values) for value, found in values)
    if unclear or conflicting:
        return {**result, "status": "review", "reason": "A possible location was found, but other premises wording is ambiguous or conflicting. Review the cited pages."}
    asset = next(asset for asset in assets if asset.pk in matches)
    return {**result, "status": "automatic", "asset_id": asset.pk,
            "reason": f"The cited premises clearly identify {asset.name}; no competing location was found."}


@transaction.atomic
def resolve_document_location(document_id):
    document = ContractDocument.objects.select_for_update().get(pk=document_id)
    record = LeaseRecord.objects.select_for_update().get(pk=document.record_id)
    last_event = document.associations.first()
    # Includes existing decisions made before automatic matching was introduced.
    if document.association_status in {"manual", "outside"} or last_event and last_event.method == "manual":
        document.association_status = "manual" if record.asset_id else "outside"
        document.association_details = {"reason": last_event.reason if last_event else "The saved manual association is retained."}
        document.save(update_fields=["association_status", "association_details"])
        return document.association_status
    automatically_owned = document.association_status == "automatic" or last_event and last_event.method == "automatic"
    if record.asset_id and not automatically_owned:
        document.association_status = "manual"
        document.association_details = {"reason": "The existing location association is retained."}
        document.save(update_fields=["association_status", "association_details"])
        return "manual"

    run = document.runs.filter(status="completed").first()
    result = evaluate_location(run, list(Asset.objects.all()))
    # Never merge into a generated unit or change a record shared by other documents.
    own_record = record.origin == "document" and not record.documents.exclude(pk=document.pk).exists()
    if result["status"] == "automatic" and not own_record:
        result.update(status="review", reason="This record is shared or belongs to the portfolio baseline. Choose its association manually.")
    target_id = result.get("asset_id") if result["status"] == "automatic" else None
    if own_record and record.asset_id != target_id:
        previous_location = record.asset.name if record.asset_id else None
        record.asset_id = target_id
        record.save(update_fields=["asset"])
        reason = result["reason"]
        if previous_location and not target_id:
            reason = f"Automatic association to {previous_location} withdrawn. {reason}"
        AssociationEvent.objects.create(document=document, previous_record_code=record.code, record_code=record.code,
            location_name=record.asset.name if target_id else "", reason=reason, user=None,
            method="automatic", evidence=result["evidence"])
    document.association_status = result["status"]
    document.association_details = result
    document.save(update_fields=["association_status", "association_details"])
    return result["status"]
