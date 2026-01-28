import json
import os
import sys
from datetime import datetime

import psycopg2

"""
Compute missing charters based on LMS updates JSON summaries.

- Reads reports/LMS_UPDATES_SINCE_OCT2025_SUMMARY.json (top_20_reserves)
- Finds current max reserve_number in almsdata charters
- Checks existence of each candidate reserve in charters
- Writes a concise report to reports/missing_charters_from_json_summary.json

Notes:
- Reserve Number is ALWAYS the Business Key
- This script is read-only except for writing the JSON report file
"""

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

INPUT_JSON = os.path.join("l:\\limo", "reports", "LMS_UPDATES_SINCE_OCT2025_SUMMARY.json")
OUTPUT_JSON = os.path.join("l:\\limo", "reports", "missing_charters_from_json_summary.json")


def parse_updates_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        reserves = []
        for item in data.get("top_20_reserves", []):
            rn = str(item.get("reserve_number", "")).strip()
            if rn:
                reserves.append(rn)
        return sorted(set(reserves))
    except Exception as e:
        print(f"❌ Could not read updates JSON: {e}")
        return []


def get_db_connection():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def get_last_alms_reserve(cur):
    cur.execute("SELECT MAX(reserve_number) FROM charters")
    row = cur.fetchone()
    last = row[0] if row and row[0] is not None else None
    return str(last) if last is not None else None


def charter_exists(cur, reserve_number):
    cur.execute("SELECT 1 FROM charters WHERE reserve_number = %s LIMIT 1", (reserve_number,))
    return cur.fetchone() is not None


def main():
    print("Scanning LMS updates JSON for candidate reserves...")
    candidates = parse_updates_json(INPUT_JSON)
    if not candidates:
        print("No candidate reserves found in JSON.")
        sys.exit(0)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        last_alms = get_last_alms_reserve(cur)
        print(f"Last almsdata reserve_number: {last_alms}")

        # Numeric compare helper (handles leading zeros)
        def to_int(s):
            try:
                return int(s)
            except Exception:
                return None

        last_int = to_int(last_alms) if last_alms is not None else None

        missing = []
        present = []
        newer = []
        for rn in candidates:
            exists = charter_exists(cur, rn)
            if exists:
                present.append(rn)
            else:
                missing.append(rn)
            if last_int is not None:
                rni = to_int(rn)
                if rni is not None and rni > last_int:
                    newer.append(rn)

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "source_json": INPUT_JSON,
            "last_alms_reserve": last_alms,
            "summary": {
                "candidates": len(candidates),
                "present_in_alms": len(present),
                "missing_in_alms": len(missing),
                "newer_than_last": len(newer),
            },
            "details": {
                "candidates": candidates,
                "present_in_alms": sorted(present),
                "missing_in_alms": sorted(missing),
                "newer_than_last": sorted(newer),
            },
            "next_actions": [
                "Option A: Create placeholder charters for missing reserves, then import charges",
                "Option B: If full LMS Reserve/Payment JSON is available, import full charters and payments",
                "Always use reserve_number as the business key",
            ],
        }

        # Write report
        try:
            with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            print(f"\n✓ Missing charter summary written to: {OUTPUT_JSON}")
            print(f"   Candidates: {len(candidates)} | Present: {len(present)} | Missing: {len(missing)} | Newer than last: {len(newer)}")
        except Exception as e:
            print(f"❌ Could not write output report: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
