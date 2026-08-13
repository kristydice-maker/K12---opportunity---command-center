import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

USAC_FRN_API = "https://opendata.usac.org/resource/qdmp-ygft.json"

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.csv"
OUTPUT_FILE = BASE_DIR / "data" / "usac_471_activity.json"
BRIEF_FILE = BASE_DIR / "data" / "erate_471_brief.md"


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


def get_frn_records(ben):
    where = (
        f"ben='{ben}' "
        f"AND funding_year in('2026','2027') "
        f"AND form_version='Current'"
    )

    params = {
        "$limit": 5000,
        "$where": where,
        "$order": "application_number DESC",
    }

    url = f"{USAC_FRN_API}?{urlencode(params)}"

    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def first_value(record, *names):
    for name in names:
        value = record.get(name)

        if value not in (None, ""):
            return str(value).strip()

    return ""


def clean_date(value):
    if not value:
        return "Not listed"

    return value[:10]


def money(value):
    if value in (None, ""):
        return "Not listed"

    try:
        return f"${float(value):,.2f}"
    except ValueError:
        return str(value)


def percent(value):
    if value in (None, ""):
        return "Not listed"

    try:
        number = float(value)

        if number <= 1:
            number *= 100

        return f"{number:.0f}%"
    except ValueError:
        return str(value)


def classify_provider(provider_name):
    provider = provider_name.lower()

    if not provider:
        return "UNKNOWN"

    if "netsync" in provider:
        return "NETSYNC"

    carrier_terms = [
        "at&t",
        "att",
        "verizon",
        "spectrum",
        "charter",
        "lumen",
        "level 3",
        "cogent",
        "unite private networks",
        "zayo",
        "frontier",
        "windstream",
        "fiberlight",
        "crown castle",
    ]

    if any(term in provider for term in carrier_terms):
        return "CARRIER"

    competitor_terms = [
        "cdw",
        "shi",
        "presidio",
        "convergeone",
        "howard",
        "dell",
        "insight",
        "connection",
        "zones",
        "computacenter",
    ]

    if any(term in provider for term in competitor_terms):
        return "COMPETITOR"

    return "UNKNOWN / OTHER"


def simplify_record(record):
    return {
        "funding_year": first_value(
            record, "funding_year"
        ),
        "form_471_application_number": first_value(
            record, "application_number"
        ),
        "frn": first_value(
            record,
            "funding_request_number",
            "frn"
        ),
        "service_type": first_value(
            record, "form_471_service_type_name"
        ),
        "funding_status": first_value(
            record, "form_471_frn_status_name"
        ),
        "service_provider": first_value(
            record, "spin_name"
        ),
        "contract_number": first_value(
            record, "contract_number"
        ),
        "establishing_form_470": first_value(
            record, "establishing_form_470"
        ),
        "service_start_date": first_value(
            record, "service_start_date"
        ),
        "service_delivery_deadline": first_value(
            record, "service_delivery_deadline"
        ),
        "contract_expiration_date": first_value(
            record, "contract_expiration_date"
        ),
        "monthly_recurring_cost": first_value(
            record, "total_monthly_recurring_eligible_costs"
        ),
        "total_pre_discount_cost": first_value(
            record, "total_pre_discount_costs"
        ),
        "funding_commitment_request": first_value(
            record, "funding_commitment_request"
        ),
        "discount_rate": first_value(
            record, "dis_pct"
        ),
        "f486_status": first_value(
            record, "f486_case_status"
        ),
    }


def generate_brief(intelligence):
    lines = [
        "# E-Rate Form 471 / FRN Outcome Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "This report summarizes current Form 471 funding requests and FRN outcomes "
        "for monitored E-Rate accounts.",
        "",
        "---",
        "",
    ]

    for account in intelligence:
        account_name = account["account_name"]
        ben = account["ben"]
        records = account["activity"]

        lines.append(f"## {account_name}")
        lines.append("")
        lines.append(f"**BEN:** {ben}")
        lines.append(f"**FRNs Found:** {len(records)}")
        lines.append("")

        if not records:
            lines.append(
                "No FY2026 or FY2027 current Form 471 / FRN activity found."
            )
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        grouped = defaultdict(list)

        for record in records:
            app_number = (
                record.get("form_471_application_number")
                or "Application number not listed"
            )

            grouped[app_number].append(record)

        for app_number, app_records in grouped.items():
            lines.append(f"### Form 471 {app_number}")
            lines.append("")

            for record in app_records:
                provider = record.get("service_provider", "")
                provider_type = classify_provider(provider)

                lines.append(
                    f"#### FRN {record.get('frn') or 'Not listed'}"
                )
                lines.append("")
                lines.append(
                    f"- **Funding Year:** "
                    f"{record.get('funding_year') or 'Not listed'}"
                )
                lines.append(
                    f"- **Service Type:** "
                    f"{record.get('service_type') or 'Not listed'}"
                )
                lines.append(
                    f"- **Funding Status:** "
                    f"{record.get('funding_status') or 'Not listed'}"
                )
                lines.append(
                    f"- **Selected Provider:** "
                    f"{provider or 'Not listed'}"
                )
                lines.append(
                    f"- **Provider Classification:** {provider_type}"
                )
                lines.append(
                    f"- **Contract Number:** "
                    f"{record.get('contract_number') or 'Not listed'}"
                )
                lines.append(
                    f"- **Establishing Form 470:** "
                    f"{record.get('establishing_form_470') or 'Not listed'}"
                )
                lines.append(
                    f"- **Service Start:** "
                    f"{clean_date(record.get('service_start_date', ''))}"
                )
                lines.append(
                    f"- **Contract Expiration:** "
                    f"{clean_date(record.get('contract_expiration_date', ''))}"
                )
                lines.append(
                    f"- **Service Delivery Deadline:** "
                    f"{clean_date(record.get('service_delivery_deadline', ''))}"
                )
                lines.append(
                    f"- **Monthly Eligible Cost:** "
                    f"{money(record.get('monthly_recurring_cost', ''))}"
                )
                lines.append(
                    f"- **Total Pre-Discount Cost:** "
                    f"{money(record.get('total_pre_discount_cost', ''))}"
                )
                lines.append(
                    f"- **Funding Request:** "
                    f"{money(record.get('funding_commitment_request', ''))}"
                )
                lines.append(
                    f"- **Discount Rate:** "
                    f"{percent(record.get('discount_rate', ''))}"
                )
                lines.append(
                    f"- **Form 486 Status:** "
                    f"{record.get('f486_status') or 'Not listed'}"
                )

                lines.append("")
                lines.append("**Competitive Interpretation:**")

                if provider_type == "NETSYNC":
                    lines.append(
                        "Netsync appears as the selected service provider for this FRN."
                    )

                elif provider_type == "CARRIER":
                    lines.append(
                        "This appears to be a carrier/connectivity award. "
                        "Treat it as account infrastructure intelligence rather than "
                        "a direct VAR competitive loss."
                    )

                elif provider_type == "COMPETITOR":
                    lines.append(
                        "A known competitor appears as the selected provider. "
                        "Review the related Form 470, equipment/services, and contract "
                        "term for future displacement or adjacent opportunities."
                    )

                else:
                    lines.append(
                        "Provider is not yet classified. Review the provider and "
                        "related Form 470 to determine competitive significance."
                    )

                lines.append("")

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
            f"Checking Form 471 / FRN activity for "
            f"{account['account_name']} (BEN {account['ben']})..."
        )

        records = get_frn_records(account["ben"])

        simplified = [
            simplify_record(record)
            for record in records
        ]

        intelligence.append({
            "account_name": account["account_name"],
            "ben": account["ben"],
            "frn_count": len(simplified),
            "activity": simplified,
        })

        print(
            f"Found {len(simplified)} FRN record(s) for "
            f"{account['account_name']}."
        )

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(intelligence, file, indent=2)

    generate_brief(intelligence)

    print(f"FRN intelligence saved to {OUTPUT_FILE}")
    print(f"Form 471 brief saved to {BRIEF_FILE}")


if __name__ == "__main__":
    main()
