import os
import sys
import csv
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    host = os.environ.get("DB_HOST", "localhost")
    name = os.environ.get("DB_NAME", "almsdata")
    user = os.environ.get("DB_USER", "postgres")
    password = os.environ.get("DB_PASSWORD", "***REDACTED***")
    port = int(os.environ.get("DB_PORT", "5432"))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def load_csv_reserves(csv_path):
    reserves = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            reserve_number = (row.get("Reserve Number") or "").strip()
            reserve_date_str = (row.get("Reserve Date") or "").strip()
            if not reserve_number:
                continue
            # zero-pad to 6 if needed
            rn = reserve_number
            if rn.isdigit() and len(rn) < 6:
                rn = rn.zfill(6)
            # parse date to date object if present
            dt = None
            if reserve_date_str:
                try:
                    dt = datetime.strptime(reserve_date_str, "%Y-%m-%d").date()
                except ValueError:
                    # Try alternative formats
                    for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
                        try:
                            dt = datetime.strptime(reserve_date_str, fmt).date()
                            break
                        except ValueError:
                            pass
            reserves.append((rn, dt))
    return reserves


def fetch_db_charters(conn, reserve_numbers):
    if not reserve_numbers:
        return {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT reserve_number, charter_date
            FROM charters
            WHERE reserve_number = ANY(%s)
            """,
            (reserve_numbers,)
        )
        rows = cur.fetchall()
    return {row["reserve_number"]: (row["charter_date"].date() if hasattr(row["charter_date"], 'date') else row["charter_date"]) for row in rows}


def main():
    # Default CSV path in repo root
    csv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "recreated_2011_charge_summary.csv"))
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]

    if not os.path.exists(csv_path):
        print(f"ERROR: CSV not found at {csv_path}")
        sys.exit(2)

    print("Verifying 2011 charge summary against database charters…")
    print(f"CSV: {csv_path}")

    reserves = load_csv_reserves(csv_path)
    csv_map = {}
    for rn, dt in reserves:
        if rn:
            csv_map[rn] = dt  # last wins, duplicates are unlikely

    reserve_list = list(csv_map.keys())
    print(f"CSV reserves: {len(reserve_list)} unique")

    conn = get_db_connection()
    try:
        db_map = fetch_db_charters(conn, reserve_list)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    found = set(db_map.keys())
    missing_in_db = [rn for rn in reserve_list if rn not in found]
    extra_in_db = [rn for rn in found if rn not in csv_map]

    date_mismatches = []
    for rn in reserve_list:
        if rn in db_map:
            csv_dt = csv_map[rn]
            db_dt = db_map[rn]
            if csv_dt and db_dt and csv_dt != db_dt:
                date_mismatches.append((rn, csv_dt, db_dt))

    print("\n=== SUMMARY ===")
    print(f"Matched in DB: {len(found)} / {len(reserve_list)}")
    print(f"Missing in DB: {len(missing_in_db)}")
    if missing_in_db:
        print("  Sample missing:")
        for rn in missing_in_db[:10]:
            print(f"   - {rn}")
    print(f"Date mismatches: {len(date_mismatches)}")
    if date_mismatches:
        print("  Sample mismatches (reserve, csv_date, db_date):")
        for tup in date_mismatches[:10]:
            print(f"   - {tup[0]}: {tup[1]} vs {tup[2]}")

    status = "PASS" if len(missing_in_db) == 0 and len(date_mismatches) == 0 else "WARN"
    print(f"\nRESULT: {status}")

    # Exit code: 0 for PASS, 1 for WARN
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
