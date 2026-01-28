#!/usr/bin/env python3
"""
Insert a single `charter_routes` row from Routing.xlsx for testing.
- Loads latest reports/ROUTING_XLSX_AUDIT_*_missing.json
- Finds a reserve_number with an existing charter but zero routes
- Inserts one route using Excel values

Usage:
  python insert_one_route_from_excel_missing.py --dry-run
  python insert_one_route_from_excel_missing.py --apply
  python insert_one_route_from_excel_missing.py --apply --reserve 015901
"""
import os
import sys
import glob
import json
from datetime import time
from typing import Optional

import psycopg2

REPORTS_DIR = r"l:/limo/reports"
MISSING_PATTERN = "ROUTING_XLSX_AUDIT_*_missing.json"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def parse_hhmm(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    try:
        parts = str(s).strip().split(":")
        h = int(parts[0]); m = int(parts[1])
        return time(hour=h, minute=m)
    except Exception:
        return None


def find_latest_missing_json() -> Optional[str]:
    candidates = sorted(glob.glob(os.path.join(REPORTS_DIR, MISSING_PATTERN)))
    return candidates[-1] if candidates else None


def main() -> int:
    apply = "--apply" in sys.argv
    reserve_arg = None
    if "--reserve" in sys.argv:
        try:
            idx = sys.argv.index("--reserve")
            reserve_arg = sys.argv[idx+1]
        except Exception:
            pass

    missing_path = find_latest_missing_json()
    if not missing_path:
        print("❌ No missing JSON found. Run verify_routing_from_excel_vs_charter_routes.py first.")
        return 1
    print(f"Using: {missing_path}")

    with open(missing_path, "r", encoding="utf-8") as f:
        missing = json.load(f)

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    target = None
    if reserve_arg:
        for rec in missing:
            reserve = rec.get("reserve_no") or rec.get("reserve")
            if reserve == reserve_arg:
                target = rec
                break
        if not target:
            print(f"❌ Reserve {reserve_arg} not found in missing list")
            cur.close(); conn.close()
            return 1
    else:
        for rec in missing:
            reserve = rec.get("reserve_no") or rec.get("reserve")
            if not reserve:
                continue
            # Try exact match first, then fallback by trimming leading zeros
            cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1", (reserve,))
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT charter_id FROM charters WHERE ltrim(reserve_number, '0') = ltrim(%s, '0') LIMIT 1", (reserve,))
                row = cur.fetchone()
            if not row:
                continue  # skip reserves without charters
            charter_id = row[0]
            cur.execute("SELECT COUNT(*) FROM charter_routes WHERE charter_id = %s", (charter_id,))
            if cur.fetchone()[0] == 0:
                target = rec
                break

    if not target:
        print("❌ No suitable reserve found (charter exists with zero routes).")
        cur.close(); conn.close()
        return 1

    reserve = target.get("reserve_no") or target.get("reserve")
    cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s LIMIT 1", (reserve,))
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT charter_id FROM charters WHERE ltrim(reserve_number, '0') = ltrim(%s, '0') LIMIT 1", (reserve,))
        row = cur.fetchone()
    if not row:
        print(f"❌ Charter not found for reserve {reserve}")
        cur.close(); conn.close()
        return 1
    charter_id = row[0]

    pickup_location = target.get("pickup")
    dropoff_location = target.get("dropoff")
    pu_time = parse_hhmm(target.get("pu_time"))
    do_time = parse_hhmm(target.get("do_time"))
    notes = target.get("notes")

    print(f"\nCandidate reserve {reserve} → charter_id {charter_id}")
    print(f"  Pickup: {pickup_location}")
    print(f"  Dropoff: {dropoff_location}")
    print(f"  PU time: {target.get('pu_time')} | DO time: {target.get('do_time')}")
    print(f"  Notes: {notes}")

    if not apply:
        print("\nDRY-RUN: Would insert one route.")
        cur.close(); conn.close()
        return 0

    cur.execute(
        """
        INSERT INTO charter_routes (
            charter_id, route_sequence, pickup_location, pickup_time,
            dropoff_location, dropoff_time, route_notes, route_status
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            charter_id,
            1,
            pickup_location,
            pu_time,
            dropoff_location,
            do_time,
            notes,
            "pending",
        ),
    )
    conn.commit()
    print("\n✅ Inserted one route from Excel for testing")
    cur.close(); conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
