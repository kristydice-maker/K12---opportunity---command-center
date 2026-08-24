import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

USAC_LINE_API = "https://opendata.usac.org/resource/hbj5-2bpj.json"

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.csv"
OUTPUT_FILE = BASE_DIR / "data" / "usac_frn_line_items.json"
BRIEF_FILE = BASE_DIR / "data" / "erate_frn_line_brief.md"


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


def get_line_items(ben):
    where = (
        f"ben='{ben}' "
        f"AND funding_year in('2026','2027') "
        f"AND form_version='Current'"
    )

    params = {
        "$limit": 5000,
        "$where": where,
    }

    url = f"{USAC_LINE_API}?{urlencode(params)}"

    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def first_value(record, *names):
    for name in names:
        value = record.get(name)

        if value not in (None, ""):
            return str(value).strip()

    return ""


def money(value):
    if value in (None, ""):
        return "Not listed"

    try:
        return f"${float(value):,.2f}"
    except ValueError:
        return str(value)


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
        "frn_line_item": first_value(
            record,
            "frn_line_item_number",
            "frn_line_item"
        ),
        "service_type": first_value(
            record,
            "form_471_service_type_name",
            "service_type"
        ),
        "function": first_value(
            record,
            "form_471_function_name",
            "function"
        ),
        "product_type": first_value(
            record,
            "form_471_product_name",
            "product_type"
        ),
        "manufacturer": first_value(
            record,
            "form_471_manufacturer_name",
            "manufacturer"
        ),
        "model": first_value(
            record,
            "model_of_equipment",
            "model"
        ),
        "unit": first_value(
            record,
            "form_471_unit_name"
        ),
        "quantity": first_value(
            record,
            "one_time_quantity",
            "monthly_quantity",
            "quantity"
        ),
        "unit_cost": first_value(
            record,
            "one_time_eligible_costs",
            "monthly_recurring_unit_eligible_costs",
            "unit_cost"
        ),
        "eligible_cost": first_value(
            record,
            "pre_discount_extended_eligible_line_item_costs",
            "total_eligible_one_time_costs",
            "total_eligible_recurring_costs"
        ),
    }


def generate_brief(intelligence):
    lines = [
        "# E-Rate FRN Line Item Brief",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Product- and service-level detail from current USAC FRN line items.",
        "",
        "---",
        "",
    ]

    for account in intelligence:
        lines.append(f"## {account['account_name']}")
        lines.append("")
        lines.append(f"**BEN:** {account['ben']}")
        lines.append(
            f"**Line Items Found:** {len(account['activity'])}"
        )
        lines.append("")

        if not account["activity"]:
            lines.append(
                "No FY2026 or FY2027 current FRN line-item activity found."
            )
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        grouped = defaultdict(list)

        for record in account["activity"]:
            frn = record.get("frn") or "FRN not listed"
            grouped[frn].append(record)

        for frn, records in grouped.items():
            lines.append(f"### FRN {frn}")
            lines.append("")

            total_eligible = 0.0

            for record in records:
                lines.append(
                    f"#### {record.get('manufacturer') or 'Manufacturer not listed'}"
                )
                lines.append("")

                if record.get("function"):
                    lines.append(
                        f"- **Function:** {record['function']}"
                    )

                if record.get("product_type"):
                    lines.append(
                        f"- **Product:** {record['product_type']}"
                    )

                if record.get("model"):
                    lines.append(
                        f"- **Model / Description:** {record['model']}"
                    )

                if record.get("quantity"):
                    lines.append(
                        f"- **Quantity:** {record['quantity']}"
                    )

                if record.get("unit"):
                    lines.append(
                        f"- **Unit:** {record['unit']}"
                    )

                if record.get("unit_cost"):
                    lines.append(
                        f"- **Eligible Unit Cost:** "
                        f"{money(record['unit_cost'])}"
                    )

                if record.get("eligible_cost"):
                    lines.append(
                        f"- **Extended Eligible Cost:** "
                        f"{money(record['eligible_cost'])}"
                    )

                    try:
                        total_eligible += float(
                            record["eligible_cost"]
                        )
                    except ValueError:
                        pass

                if record.get("service_type"):
                    lines.append(
                        f"- **Service Type:** {record['service_type']}"
                    )

                lines.append("")

            lines.append(
                f"**FRN Line-Item Eligible Total:** "
                f"{money(total_eligible)}"
            )
            lines.append("")

            manufacturers = sorted({
                record.get("manufacturer", "")
                for record in records
                if record.get("manufacturer")
            })

            if manufacturers:
                lines.append(
                    f"**Manufacturers Identified:** "
                    f"{', '.join(manufacturers)}"
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

    print(
        f"Monitoring FRN line items for "
        f"{len(accounts)} E-Rate accounts..."
    )

    for account in accounts:
        print(
            f"Checking FRN line items for "
            f"{account['account_name']} "
            f"(BEN {account['ben']})..."
        )

        records = get_line_items(account["ben"])

        simplified = [
            simplify_record(record)
            for record in records
        ]

        intelligence.append({
            "account_name": account["account_name"],
            "ben": account["ben"],
            "line_item_count": len(simplified),
            "activity": simplified,
        })

        print(
            f"Found {len(simplified)} line item(s) for "
            f"{account['account_name']}."
        )

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(intelligence, file, indent=2)

    generate_brief(intelligence)

    print(
        f"FRN line-item intelligence saved to {OUTPUT_FILE}"
    )
    print(
        f"FRN line-item brief saved to {BRIEF_FILE}"
    )


if __name__ == "__main__":
    main()
