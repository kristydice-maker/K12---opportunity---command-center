import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

FORM_470_FILE = BASE_DIR / "data" / "usac_470_activity.json"
FORM_471_FILE = BASE_DIR / "data" / "usac_471_activity.json"
LINE_ITEM_FILE = BASE_DIR / "data" / "usac_frn_line_items.json"

OUTPUT_FILE = BASE_DIR / "data" / "erate_account_intelligence.md"


def load_json(path):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def money(value):
    if value in (None, ""):
        return "Not listed"

    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)


def clean_date(value):
    if not value:
        return "Not listed"

    return str(value)[:10]


def account_map(dataset):
    return {
        item.get("account_name"): item
        for item in dataset
        if item.get("account_name")
    }


def classify_provider(provider):
    text = (provider or "").lower()

    if "netsync" in text:
        return "NETSYNC"

    carrier_terms = [
        "unite private networks",
        "zayo",
        "at&t",
        "att",
        "verizon",
        "spectrum",
        "charter",
        "lumen",
        "frontier",
        "windstream",
        "fiberlight",
        "crown castle",
        "millennium telcom",
        "capco communications",
    ]

    if any(term in text for term in carrier_terms):
        return "CARRIER"

    competitor_terms = [
        "govconnection",
        "connection",
        "cdw",
        "shi",
        "presidio",
        "convergeone",
        "howard",
        "dell",
        "insight",
        "zones",
        "computacenter",
    ]

    if any(term in text for term in competitor_terms):
        return "COMPETITOR"

    return "UNKNOWN / OTHER"


def score_account(form470_records, frn_records):
    score = 0
    reasons = []

    for record in frn_records:
        service_type = (
            record.get("service_type") or ""
        ).lower()

        provider = record.get("service_provider") or ""
        provider_type = classify_provider(provider)

        try:
            total_cost = float(
                record.get("total_pre_discount_cost") or 0
            )
        except ValueError:
            total_cost = 0

        if "internal connections" in service_type:
            score += 40
            reasons.append(
                "Current Internal Connections funding"
            )

        if provider_type == "COMPETITOR":
            score += 30
            reasons.append(
                f"Known competitor selected: {provider}"
            )

        if provider_type == "NETSYNC":
            score += 20
            reasons.append(
                "Netsync selected on current FRN"
            )

        if total_cost >= 500000:
            score += 20
            reasons.append(
                "Large E-Rate project over $500K"
            )

        elif total_cost >= 100000:
            score += 10
            reasons.append(
                "E-Rate project over $100K"
            )

    for record in form470_records:
        funding_year = record.get("funding_year")

        if funding_year == "2027":
            score += 25
            reasons.append(
                "FY2027 Form 470 activity"
            )

    unique_reasons = []

    for reason in reasons:
        if reason not in unique_reasons:
            unique_reasons.append(reason)

    return score, unique_reasons


def priority_label(score):
    if score >= 70:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    if score > 0:
        return "WATCH"
    return "LOW"


def group_line_items_by_frn(records):
    grouped = defaultdict(list)

    for record in records:
        frn = record.get("frn")

        if frn:
            grouped[frn].append(record)

    return grouped


def product_summary(records):
    summaries = []

    for record in records:
        manufacturer = record.get("manufacturer") or ""
        function = record.get("function") or ""
        model = record.get("model") or ""
        quantity = record.get("quantity") or ""
        eligible_cost = record.get("eligible_cost") or ""

        parts = []

        if manufacturer:
            parts.append(manufacturer)

        if function:
            parts.append(function)

        if model:
            parts.append(model)

        if quantity:
            parts.append(f"Qty {quantity}")

        if eligible_cost:
            parts.append(
                f"Eligible cost {money(eligible_cost)}"
            )

        summary = " | ".join(parts)

        if summary and summary not in summaries:
            summaries.append(summary)

    return summaries


def recommended_action(form470_records, frn_records):
    internal_competitor = []

    carrier_records = []

    for record in frn_records:
        provider = record.get("service_provider") or ""
        provider_type = classify_provider(provider)

        service_type = (
            record.get("service_type") or ""
        ).lower()

        if (
            "internal connections" in service_type
            and provider_type == "COMPETITOR"
        ):
            internal_competitor.append(record)

        if provider_type == "CARRIER":
            carrier_records.append(record)

    if internal_competitor:
        record = internal_competitor[0]

        return (
            "Competitive action: review the awarded technology, "
            f"provider footprint ({record.get('service_provider')}), "
            "contract term, and adjacent services. Build a displacement "
            "or expansion strategy well before the next refresh cycle."
        )

    if any(
        record.get("funding_year") == "2027"
        for record in form470_records
    ):
        return (
            "Active pursuit: review FY2027 Form 470 activity and attached "
            "RFPs for opportunities that align with Netsync solutions."
        )

    if carrier_records:
        expirations = [
            clean_date(
                record.get("contract_expiration_date")
            )
            for record in carrier_records
            if record.get("contract_expiration_date")
        ]

        if expirations:
            return (
                "Account intelligence: current activity is primarily "
                "carrier/connectivity. Track contract expirations "
                f"({', '.join(sorted(set(expirations)))}) for future "
                "WAN, routing, optics, resiliency, and services planning."
            )

        return (
            "Account intelligence: current E-Rate activity is primarily "
            "carrier/connectivity. Use it to understand WAN architecture "
            "and identify adjacent infrastructure opportunities."
        )

    if form470_records or frn_records:
        return (
            "Review the current E-Rate activity for adjacent technology, "
            "services, competitive, or lifecycle opportunities."
        )

    return (
        "No current FY2026/FY2027 E-Rate signal. Maintain normal account "
        "cadence
