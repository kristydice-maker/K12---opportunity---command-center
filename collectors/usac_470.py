import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

USAC_API = "https://opendata.usac.org/resource/jt8s-3q52.json"

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.csv"
OUTPUT_FILE = BASE_DIR / "data" / "usac_470_activity.json"
BRIEF_FILE = BASE_DIR / "data" / "erate_brief.md"


def load_accounts():
    accounts = []

    with ACCOUNTS_FILE.open("r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            ben = row.get("ben", "").strip()
            eligible = row.get("erate_eligible", "").strip().lower()

            if ben and eligible == "yes":
                accounts.append({
                    "account_name": row["account_name"],
                    "ben": ben,
                })

    return accounts


def get_form_470_records(ben):
    where = (
        f"billed_entity_number='{ben}' "
        f"AND funding_year in('2026','2027') "
        f"AND form_version='Current'"
    )

    params = {
        "$limit": 5000,
        "$where": where,
        "$order": "certified_date_time DESC",
    }

    url = f"{USAC_API}?{urlencode(params)}"

    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_value(value):
    if value in (None, ""):
        return ""

    if isinstance(value, dict):
        if value.get("url"):
            return str(value["url"]).strip()

        if value.get("description"):
            return str(value["description"]).strip()

        return ""

    if isinstance(value, list):
        cleaned = []

        for item in value:
            result = normalize_value(item)

            if result:
                cleaned.append(result)

        return ", ".join(cleaned)

    return str(value).strip()


def first_value(record, *names):
    for name in names:
        value = normalize_value(record.get(name))

        if value:
            return value

    return ""


def simplify_record(record):
    return {
        "application_number": first_value(
            record, "application_number"
        ),
        "funding_year": first_value(
            record, "funding_year"
        ),
        "status": first_value(
            record, "fcc_form_470_status"
        ),
        "certified_date": first_value(
            record, "certified_date_time"
        ),
        "allowable_contract_date": first_value(
            record, "allowable_contract_date"
        ),
        "service_type": first_value(
            record, "service_type"
        ),
        "function": first_value(
            record, "function"
        ),
        "manufacturer": first_value(
            record, "manufacturer"
        ),
        "quantity": first_value(
            record, "quantity"
        ),
        "form_pdf": first_value(
            record, "form_pdf"
        ),
        "rfp_documents": first_value(
            record, "rfp_documents"
        ),
        "consultant": first_value(
            record,
            "consulting_firm_name",
            "consultant_name"
        ),
    }


def clean_date(value):
    if not value:
        return "Not listed"

    return value[:10]


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date()
    except ValueError:
        return None


def unique_values(records, field):
    values = []

    for record in records:
        value = record.get(field, "").strip()

        if value and value not in values:
            values.append(value)

    return values


def classify_opportunity(records):
    text_parts = []

    for record in records:
        text_parts.extend([
            record.get("service_type", ""),
            record.get("function", ""),
            record.get("manufacturer", ""),
        ])

    text = " ".join(text_parts).lower()

    if any(word in text for word in [
        "switch",
        "wireless",
        "router",
        "network",
        "ethernet",
        "lan",
    ]):
        return "Networking"

    if any(word in text for word in [
        "firewall",
        "security",
        "cyber",
        "filtering",
        "authentication",
    ]):
        return "Cybersecurity"

    if any(word in text for word in [
        "fiber",
        "internet",
        "broadband",
        "transport",
        "wan",
    ]):
        return "Connectivity / WAN"

    if any(word in text for word in [
        "ups",
        "battery",
        "power",
    ]):
        return "Power / Infrastructure"

    return "General E-Rate"


def determine_solution_fit(records):
    if not records:
        return "NONE"

    opportunity = classify_opportunity(records)

    if opportunity in {
        "Networking",
        "Cybersecurity",
        "Connectivity / WAN",
        "Power / Infrastructure",
    }:
        return "HIGH"

    return "REVIEW"


def determine_timing(records):
    if not records:
        return "NO CURRENT ACTIVITY"

    today = datetime.now(timezone.utc).date()

    dates = []

    for record in records:
        date_value = parse_date(
            record.get("allowable_contract_date", "")
        )

        if date_value:
            dates.append(date_value)

    if not dates:
        return "REVIEW DATE"

    latest_acd = max(dates)

    if today < latest_acd:
        return "PRE-ACD"

    days_since_acd = (today - latest_acd).days

    if days_since_acd <= 90:
        return "AWARD / FOLLOW-UP"

    return "HISTORICAL REVIEW"


def sales_action(opportunity, timing):
    if timing == "PRE-ACD":
        timing_action = (
            "Review the Form 470 and RFP promptly. The Allowable Contract "
            "Date has not yet passed."
        )

    elif timing == "AWARD / FOLLOW-UP":
        timing_action = (
            "The Allowable Contract Date has passed recently. Check for "
            "award activity, Form 471 filings, board approval, and customer follow-up."
        )

    else:
        timing_action = (
            "Treat this Form 470 as historical intelligence. Check Form 471 "
            "and FRN data to determine what was ultimately purchased and who won."
        )

    if opportunity == "Networking":
        solution_action = (
            "The requested technology aligns with Netsync networking capabilities, "
            "including switching, wireless, routing, licensing, and services."
        )

    elif opportunity == "Cybersecurity":
        solution_action = (
            "Review fit for firewall, identity, filtering, managed security, "
            "and related cybersecurity solutions."
        )

    elif opportunity == "Connectivity / WAN":
        solution_action = (
            "Review fiber, WAN, carrier, transport, optics, routing, and "
            "implementation opportunities."
        )

    elif opportunity == "Power / Infrastructure":
        solution_action = (
            "Review UPS, network closet, resiliency, and related infrastructure needs."
        )

    else:
        solution_action = (
            "Review the Form 470 and RFP for relevant Netsync products and services."
        )

    return f"{timing_action} {solution_action}"


def generate_brief(intelligence):
    lines = [
        "# E-Rate Opportunity Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Current USAC Form 470 intelligence for monitored accounts.",
        "",
        "> Note: Allowable Contract Date (ACD) is a USAC E-Rate milestone, "
        "not necessarily the customer's bid-response deadline.",
        "",
        "---",
        "",
    ]

    for account in intelligence:
        account_name = account["account_name"]
        ben = account["ben"]
        records = account["activity"]

        opportunity = classify_opportunity(records)
        solution_fit = determine_solution_fit(records)
        timing = determine_timing(records)

        lines.append(f"## {account_name}")
        lines.append("")
        lines.append(f"**BEN:** {ben}")
        lines.append(f"**Solution Fit:** {solution_fit}")
        lines.append(f"**Opportunity Type:** {opportunity}")
        lines.append(f"**Opportunity Timing:** {timing}")
        lines.append("")

        if not records:
            lines.append(
                "No FY2026 or FY2027 current Form 470 activity found."
            )
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        applications = defaultdict(list)

        for record in records:
            app_number = (
                record.get("application_number")
                or "Application number not listed"
            )

            applications[app_number].append(record)

        for app_number, app_records in applications.items():
            first = app_records[0]

            funding_year = first.get("funding_year") or "Not listed"
            certified = clean_date(
                first.get("certified_date", "")
            )
            contract_date = clean_date(
                first.get("allowable_contract_date", "")
            )
            status = first.get("status") or "Not listed"

            services = unique_values(
                app_records, "service_type"
            )
            functions = unique_values(
                app_records, "function"
            )
            manufacturers = unique_values(
                app_records, "manufacturer"
            )
            consultants = unique_values(
                app_records, "consultant"
            )
            rfp_documents = unique_values(
                app_records, "rfp_documents"
            )
            form_pdfs = unique_values(
                app_records, "form_pdf"
            )

            app_opportunity = classify_opportunity(app_records)
            app_timing = determine_timing(app_records)

            lines.append(f"### Form 470 {app_number}")
            lines.append("")
            lines.append(f"- **Funding Year:** {funding_year}")
            lines.append(f"- **Status:** {status}")
            lines.append(f"- **Certified:** {certified}")
            lines.append(
                f"- **Allowable Contract Date:** {contract_date}"
            )
            lines.append(
                f"- **Timing:** {app_timing}"
            )

            if services:
                lines.append(
                    f"- **Service Type:** {', '.join(services)}"
                )

            if functions:
                lines.append(
                    f"- **Requested Functions:** {', '.join(functions)}"
                )

            if manufacturers:
                lines.append(
                    f"- **Manufacturer:** {', '.join(manufacturers)}"
                )

            if consultants:
                lines.append(
                    f"- **Consultant:** {', '.join(consultants)}"
                )

            if form_pdfs:
                lines.append(
                    f"- **Form 470:** [Open USAC Form 470]({form_pdfs[0]})"
                )

            if rfp_documents:
                lines.append(
                    f"- **RFP:** [Open RFP Document]({rfp_documents[0]})"
                )
            else:
                lines.append(
                    "- **RFP:** None listed"
                )

            lines.append("")
            lines.append("**Suggested Sales Action:**")
            lines.append(
                sales_action(app_opportunity, app_timing)
            )
            lines.append("")

        lines.append("---")
        lines.append("")

    BRIEF_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


def main():
    accounts = load_accounts()
    intelligence = []

    print(f"Monitoring {len(accounts)} E-Rate accounts...")

    for account in accounts:
        print(
            f"Checking {account['account_name']} "
            f"(BEN {account['ben']})..."
        )

        records = get_form_470_records(account["ben"])

        simplified = [
            simplify_record(record)
            for record in records
        ]

        intelligence.append({
            "account_name": account["account_name"],
            "ben": account["ben"],
            "active_470_rows": len(simplified),
            "activity": simplified,
        })

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(intelligence, file, indent=2)

    generate_brief(intelligence)

    print(f"JSON intelligence saved to {OUTPUT_FILE}")
    print(f"E-Rate brief saved to {BRIEF_FILE}")


if __name__ == "__main__":
    main()
