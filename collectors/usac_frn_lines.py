import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

USAC_LINE_API = "https://opendata.usac.org/resource/hbj5-2bpj.json"

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.csv"
OUTPUT_FILE = BASE_DIR / "data" / "usac_frn_line_items.json"


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
            "function",
            "function_type"
        ),
        "product_type": first_value(
            record,
            "product_type",
            "type_of_product"
        ),
        "manufacturer": first_value(
            record,
            "manufacturer"
        ),
        "model": first_value(
            record,
            "model",
            "model_number"
        ),
        "quantity": first_value(
            record,
            "quantity"
        ),
        "unit_cost": first_value(
            record,
            "unit_cost"
        ),
        "total_cost": first_value(
            record,
            "total_cost",
            "total_pre_discount_costs"
        ),
        "eligible_cost": first_value(
            record,
            "eligible_cost",
            "total_eligible_cost"
        ),

        # Temporary diagnostic fields.
        # These let us see the exact USAC column names
        # for useful product and cost information.
        "raw_useful_fields": {
            key: value
            for key, value in record.items()
            if any(term in key.lower() for term in [
                "frn",
                "function",
                "product",
                "manufacturer",
                "make",
                "model",
                "quantity",
                "unit",
                "cost",
                "eligible",
                "service",
            ])
        },
    }


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

    print(
        f"FRN line-item intelligence saved to {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
