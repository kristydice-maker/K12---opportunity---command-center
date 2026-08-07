import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

# USAC E-Rate Form 470 Open Data dataset
USAC_API = "https://opendata.usac.org/resource/jt8s-3q52.json"

BASE_DIR = Path(__file__).resolve().parent.parent
ACCOUNTS_FILE = BASE_DIR / "data" / "accounts.csv"
OUTPUT_FILE = BASE_DIR / "data" / "usac_470_activity.json"


def load_accounts():
    """Load E-Rate eligible pilot accounts that have a BEN."""
    accounts = []

    with ACCOUNTS_FILE.open("r", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            ben = row.get("ben", "").strip()
            eligible = row.get("erate_eligible", "").strip().lower()

            if ben and eligible == "yes":
                accounts.append(
                    {
                        "account_name": row["account_name"],
                        "ben": ben,
                    }
                )

    return accounts


def get_form_470_records(ben):
    """Retrieve Form 470 records from USAC for one BEN."""
    params = {
    "$limit": 5000,
    "$where": f"billed_entity_number='{ben}'",
}

    url = f"{USAC_API}?{urlencode(params)}"

    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    accounts = load_accounts()
    results = []

    print(f"Monitoring {len(accounts)} E-Rate accounts...")

    for account in accounts:
        print(
            f"Checking USAC Form 470 activity for "
            f"{account['account_name']} (BEN {account['ben']})..."
        )

        records = get_form_470_records(account["ben"])

        results.append(
            {
                "account_name": account["account_name"],
                "ben": account["ben"],
                "record_count": len(records),
                "form_470_records": records,
            }
        )

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print(f"Finished. Results saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
