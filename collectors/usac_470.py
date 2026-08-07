import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

USAC_API = "https://opendata.usac.org/resource/jt8s-3q52.json"

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.csv"
OUTPUT_FILE = BASE_DIR / "data" / "usac_470_activity.json"

# Keep the current and upcoming E-Rate years.
TRACK_FUNDING_YEARS = {"2026", "2027"}


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

        # A Form 470 can have multiple service-request rows.
        # Keep each row for now, but only retain sales-useful fields.
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

    print(f"Finished. Intelligence saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
