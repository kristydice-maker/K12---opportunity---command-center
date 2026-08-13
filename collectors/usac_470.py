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


def first_value(record, *names):
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return str(value).strip()
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

    try:
        return value[:10]
    except Exception:
        return value


def unique_values(records, field):
    values = []

    for record in records:
        value = record.get(field, "").strip()

        if value and value not in values:
            values.append(value)

    return values


def determine_priority(records):
    if not records:
        return "NO CURRENT ACTIVITY"

    today = datetime.now(timezone.utc).date()

    future_deadlines = []

    for record in records:
        value = record.get("allowable_contract_date", "")

        if value:
            try:
                deadline = datetime.fromisoformat(
                    value.replace("Z", "+00:00")
                ).date()

                if deadline >= today:
                    future_deadlines.append(deadline)
            except ValueError:
                pass

    if future_deadlines:
        days_until = min(
            (deadline - today).days
            for deadline in future_deadlines
        )

        if days_until <= 30:
            return "HIGH"
        elif days_until <= 60:
            return "MEDIUM"

    return "REVIEW"


def generate_brief(intelligence):
    lines = [
        "# E-Rate Opportunity Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "This report summarizes current USAC Form 470 activity for monitored accounts.",
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
        
lines.append(
    f"**Sales Priority:** {determine_priority(records)}"
)
lines.append(
    f"**Opportunity Type:** {classify_opportunity(records)}"
)
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

            lines.append(f"### Form 470 {app_number}")
            lines.append("")
            lines.append(f"- **Funding Year:** {funding_year}")
            lines.append(f"- **Status:** {status}")
            lines.append(f"- **Certified:** {certified}")
            lines.append(
                f"- **Allowable Contract Date:** {contract_date}"
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

            lines.append(
                f"- **RFP Documents:** "
                f"{'Available' if rfp_documents else 'None listed'}"
            )

            if form_pdfs:
                lines.append(
                    f"- **Form 470 PDF:** {form_pdfs[0]}"
                )

            if rfp_documents:
                lines.append(
                    f"- **RFP Link/Data:** {rfp_documents[0]}"
                )

            lines.append("")
            lines.append("**Suggested Sales Action:**")

            opportunity = classify_opportunity(app_records)

            if opportunity == "Networking":
                lines.append(
                    "Review the RFP for switching, wireless, routing, and related "
                    "infrastructure. Compare against the existing account technology "
                    "strategy and identify a Netsync design or refresh opportunity."
                )

            elif opportunity == "Cybersecurity":
                lines.append(
                    "Review security requirements and determine fit for firewall, "
                    "identity, filtering, managed security, or related Netsync solutions."
                )

            elif opportunity == "Connectivity / WAN":
                lines.append(
                    "Review carrier, fiber, WAN, and transport requirements and determine "
                    "whether Netsync can influence architecture, optics, routing, or "
                    "implementation services."
                )

            elif opportunity == "Power / Infrastructure":
                lines.append(
                    "Review UPS and infrastructure requirements for related data center, "
                    "network closet, and resiliency opportunities."
                )

            else:
                lines.append(
                    "Review the Form 470 and attached RFP to determine whether there is "
                    "a relevant Netsync solution or services opportunity."
                )

            lines.append("")
            
            if manufacturers:
                lines.append(
                    f"Review requested manufacturers "
                    f"({', '.join(manufacturers)}) against Netsync "
                    f"solutions and incumbent vendor position."
                )
            else:
                lines.append(
                    "Review the Form 470 and attached RFP for networking, "
                    "cybersecurity, data center, cloud, collaboration, "
                    "A/V, and safety/security opportunities."
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
