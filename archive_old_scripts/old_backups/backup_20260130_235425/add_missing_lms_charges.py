#!/usr/bin/env python
"""
Add missing charter charges from LMS (Access) into almsdata (PostgreSQL).

- Compares LMS Charge rows to almsdata charter_charges by reserve_number, amount, description.
- Uses diffs from reports/lms_vs_alms_charges.json (already generated).
- Dry-run by default; use --write to commit inserts.
- Never deletes; only inserts missing rows.
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime

import pyodbc
import psycopg2

MDB_FILE = r"L:\limo\backups\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DIFF_FILE = r"L:\limo\reports\lms_vs_alms_charges.json"


def connect_mdb():
    conn_str = f"Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={MDB_FILE};"
    return pyodbc.connect(conn_str)


def connect_pg():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


# Hard guard: respect no-LMS-sync policy
if os.getenv('DISABLE_LMS_SYNC') == '1' or os.path.exists(r"L:\limo\CONFIG_NO_LMS_SYNC.txt"):
    print("❌ LMS sync disabled: skipping add_missing_lms_charges.py")
    sys.exit(0)


def load_positive_deltas(limit=None, min_delta=0.01):
    if not os.path.exists(DIFF_FILE):
        raise FileNotFoundError(DIFF_FILE)
    with open(DIFF_FILE, "r", encoding="utf-8") as f:
        diffs = json.load(f)["differences"]
    pos = [d for d in diffs if d.get("delta_charge_totals", 0) > min_delta]
    if limit:
        pos = pos[:limit]
    return pos


def fetch_lms_charges_for_reserve(cur, reserve_no):
    cur.execute(
        "SELECT ChargeID, Reserve_No, Amount, Desc, LastUpdated, LastUpdatedBy FROM Charge WHERE Reserve_No = ?",
        reserve_no,
    )
    rows = cur.fetchall()
    charges = []
    for r in rows:
        charges.append(
            {
                "charge_id": r[0],
                "reserve_no": str(r[1]).strip() if r[1] is not None else None,
                "amount": float(r[2]) if r[2] is not None else 0.0,
                "description": (r[3] or "").strip(),
                "last_updated": r[4],
                "last_updated_by": r[5],
            }
        )
    return charges


def fetch_pg_charges_for_reserve(cur, reserve_no):
    cur.execute(
        "SELECT charge_id, amount, COALESCE(description,'') FROM charter_charges WHERE reserve_number = %s",
        (reserve_no,),
    )
    rows = cur.fetchall()
    return [
        {
            "charge_id": r[0],
            "amount": float(r[1]) if r[1] is not None else 0.0,
            "description": (r[2] or "").strip(),
        }
        for r in rows
    ]


def map_charter_id(cur, reserve_no):
    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_no,))
    row = cur.fetchone()
    return row[0] if row else None


def multiset_counts(charges):
    return Counter((round(c["amount"], 2), c["description"].lower()) for c in charges)


def build_inserts(lms_rows, pg_rows, reserve_no, charter_id):
    inserts = []
    lms_counts = multiset_counts(lms_rows)
    pg_counts = multiset_counts(pg_rows)

    for key, lms_count in lms_counts.items():
        pg_count = pg_counts.get(key, 0)
        missing = lms_count - pg_count
        if missing > 0:
            amount, desc = key
            # pick representative rows to insert (missing times)
            for _ in range(missing):
                inserts.append(
                    {
                        "reserve_number": reserve_no,
                        "charter_id": charter_id,
                        "amount": amount,
                        "gst_amount": 0.0,
                        "description": desc[:200] if desc else None,
                        "created_at": datetime.utcnow().isoformat(),
                        "last_updated_by": "lms_sync",
                    }
                )
    return inserts


def insert_charges(cur, rows):
    if not rows:
        return 0
    sql = (
        "INSERT INTO charter_charges (reserve_number, charter_id, amount, gst_amount, description, created_at, last_updated_by) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    params = [
        (
            r["reserve_number"],
            r["charter_id"],
            r["amount"],
            r["gst_amount"],
            r["description"],
            r["created_at"],
            r["last_updated_by"],
        )
        for r in rows
    ]
    cur.executemany(sql, params)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Add missing charges from LMS to almsdata")
    parser.add_argument("--write", action="store_true", help="Commit inserts (default is dry-run)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of reserves to process (for testing)")
    parser.add_argument("--min-delta", type=float, default=0.01, help="Minimum positive delta to consider")
    args = parser.parse_args()

    diffs = load_positive_deltas(limit=args.limit, min_delta=args.min_delta)
    print(f"Processing {len(diffs)} reserves with positive LMS>almsdata charge deltas")

    mdb_conn = connect_mdb()
    pg_conn = connect_pg()
    mdb_cur = mdb_conn.cursor()
    pg_cur = pg_conn.cursor()

    total_inserts = 0
    reserves_with_inserts = 0
    failed = []

    try:
        for idx, d in enumerate(diffs, 1):
            res = d["reserve_number"]
            lms_rows = fetch_lms_charges_for_reserve(mdb_cur, res)
            pg_rows = fetch_pg_charges_for_reserve(pg_cur, res)
            charter_id = map_charter_id(pg_cur, res)

            if not charter_id:
                failed.append((res, "No charter_id in almsdata"))
                continue

            inserts = build_inserts(lms_rows, pg_rows, res, charter_id)
            if not inserts:
                continue

            print(f"[{idx}/{len(diffs)}] {res}: inserting {len(inserts)} missing charges")
            if args.write:
                insert_charges(pg_cur, inserts)
            total_inserts += len(inserts)
            reserves_with_inserts += 1

        if args.write:
            pg_conn.commit()
            print(f"\n✓ Committed {total_inserts} inserted charges across {reserves_with_inserts} reserves")
        else:
            print(f"\n(DRY-RUN) Would insert {total_inserts} charges across {reserves_with_inserts} reserves. Re-run with --write to apply.")

        if failed:
            print("\nReserves skipped:")
            for res, reason in failed[:20]:
                print(f"  {res}: {reason}")
            if len(failed) > 20:
                print(f"  ... {len(failed)-20} more")

    finally:
        mdb_conn.close()
        pg_conn.close()


if __name__ == "__main__":
    main()
