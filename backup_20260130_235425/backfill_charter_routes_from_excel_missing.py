#!/usr/bin/env python3
"""
Backfill missing charter_routes from the latest ROUTING_XLSX_AUDIT_*_missing.json.
- Reads the most recent missing.json produced by verify_routing_from_excel_vs_charter_routes.py
- For each reserve_number with routing, inserts a single route line if none exists
- Uses reserve_number (business key) to locate charters

Usage:
  python backfill_charter_routes_from_excel_missing.py --apply
  (omit --apply for dry-run)
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
    missing_path = find_latest_missing_json()
    if not missing_path:
        print("❌ No missing JSON found. Run verify_routing_from_excel_vs_charter_routes.py first.")
        return 1
    print(f"Using: {missing_path}")

    with open(missing_path, "r", encoding="utf-8") as f:
        missing = json.load(f)

    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "***REDACTED***"),
    )
    cur = conn.cursor()

    inserted = 0
    skipped_has_routes = 0
    skipped_no_charter = 0

    for rec in missing:
        reserve = rec.get("reserve_no") or rec.get("reserve")
        if not reserve:
            continue
        # Find charter_id
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
        row = cur.fetchone()
        if not row:
            skipped_no_charter += 1
            continue
        charter_id = row[0]
        # Check existing routes
        cur.execute("SELECT COUNT(*) FROM charter_routes WHERE charter_id = %s", (charter_id,))
        if cur.fetchone()[0] > 0:
            skipped_has_routes += 1
            continue
        # Prepare values
        pickup_location = rec.get("pickup")
        dropoff_location = rec.get("dropoff")
        pu_time = parse_hhmm(rec.get("pu_time"))
        do_time = parse_hhmm(rec.get("do_time"))
        notes = rec.get("notes")
        # Ensure at least one field present
        if not any([pickup_location, dropoff_location, pu_time, do_time, notes]):
            continue
        if apply:
            cur.execute(
                """
                INSERT INTO charter_routes (
                    charter_id, route_sequence, pickup_location, pickup_time,
                    dropoff_location, dropoff_time, estimated_duration_minutes,
                    actual_duration_minutes, estimated_distance_km, actual_distance_km,
                    route_price, route_notes, route_status
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    charter_id,
                    1,
                    pickup_location,
                    pu_time,
                    dropoff_location,
                    do_time,
                    None,
                    None,
                    None,
                    None,
                    None,
                    notes,
                    "pending",
                ),
            )
            inserted += 1
        else:
            print(f"DRY-RUN: Would insert route for reserve {reserve} → charter_id {charter_id}")

    if apply:
        conn.commit()
    cur.close(); conn.close()

    print("\n✅ Backfill complete" if apply else "\n✅ Dry-run complete")
    print(f"   Inserted: {inserted}")
    print(f"   Skipped (existing routes): {skipped_has_routes}")
    print(f"   Skipped (no charter): {skipped_no_charter}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
