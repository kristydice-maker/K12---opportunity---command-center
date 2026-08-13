import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

USAC_FRN_API = "https://opendata.usac.org/resource/qdmp-ygft.json"

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.csv"
OUTPUT_FILE = BASE_DIR / "data" / "usac_471_activity.json"


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
            record,
            "form_471_service_type_name",
            "service_type_name",
            "service_type"
        ),

        "funding_status": first_value(
            record,
            "form_471_frn_status_name",
            "frn_status_name",
            "funding_status"
        ),

        "service_provider": first_value(
            record,
            "spin_name",
            "service_provider_name"
        ),

        "spin": first_value(
            record,
            "spin",
            "service_provider_number"
        ),

        "contract_number": first_value(
            record,
            "contract_number"
        ),

        "funding_commitment_request": first_value(
            record,
            "funding_commitment_request",
            "funding_commitment_request_amount"
        ),

        "committed_amount": first_value(
            record,
            "funding_commitment_amount",
            "committed_amount"
        ),

        "discount_rate": first_value(
            record,
            "dis_pct",
            "discount_rate"
        ),

        "form_470_number": first_value(
            record,
            "establishing_fcc_form_470",
            "form_470_number"
        ),

        "raw_useful_fields": {
            key: value
            for key, value in record.items()
            if any(term in key.lower() for term in [
                "service",
                "spin",
                "provider",
                "status",
                "discount",
                "commit",
                "cost",
                "470",
                "contract",
            ])
        },
    }


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

    print(f"FRN intelligence saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
