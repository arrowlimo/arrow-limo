#!/usr/bin/env python3
"""
Create placeholder `charters` for reserves found in the latest Routing.xlsx audit
that have routing data but no existing charter. This unblocks route backfill.

- Sources: reports/ROUTING_XLSX_AUDIT_*_missing.json
- Business key: reserve_number
- Idempotent: skips reserves that already have a charter
- Modes: --dry-run (default) or --apply
"""
import os
import sys
import glob
import json
from datetime import datetime, UTC

import psycopg2

REPORTS_DIR = r"l:/limo/reports"
MISSING_PATTERN = "ROUTING_XLSX_AUDIT_*_missing.json"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def find_latest_missing_json():
    candidates = sorted(glob.glob(os.path.join(REPORTS_DIR, MISSING_PATTERN)))
    return candidates[-1] if candidates else None


def main() -> int:
    apply_mode = ("--apply" in sys.argv or "--yes" in sys.argv)
    dry_run = ("--dry-run" in sys.argv) or (not apply_mode)

    missing_path = find_latest_missing_json()
    if not missing_path:
        print("❌ No missing JSON found. Run verify_routing_from_excel_vs_charter_routes.py first.")
        return 1
    print(f"Using: {missing_path}")

    with open(missing_path, "r", encoding="utf-8") as f:
        missing = json.load(f)

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    to_create = []
    for rec in missing:
        reserve = rec.get("reserve_no") or rec.get("reserve")
        if not reserve:
            continue
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve,))
        row = cur.fetchone()
        if row:
            continue
        to_create.append(reserve)

    # Deduplicate reserves in case multiple rows exist per reserve
    to_create = sorted(set(to_create))

    print("\nPLACEHOLDER CHARTERS PREVIEW")
    print("- Total reserves in missing list:", len(missing))
    print("- Without existing charters:", len(to_create))
    for r in to_create[:20]:
        print("  •", r)
    if len(to_create) > 20:
        print(f"  … and {len(to_create)-20} more")

    if dry_run:
        print("\n⚠️ Dry-run: no changes made. Pass --apply to insert placeholders.")
        cur.close(); conn.close()
        return 0

    print("\nAPPLYING PLACEHOLDER CHARTERS")
    created = 0
    now = datetime.now(UTC)

    for reserve in to_create:
        try:
            cur.execute(
                """
                INSERT INTO charters (
                    reserve_number,
                    charter_date,
                    total_amount_due,
                    balance,
                    driver_paid,
                    driver_gratuity,
                    status,
                    created_at,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING charter_id
                """,
                (
                    reserve,
                    now.date(),
                    0.0,
                    0.0,
                    False,
                    0.0,
                    'placeholder',
                    now,
                    now,
                ),
            )
            new_id = cur.fetchone()[0]
            created += 1
            print(f"✅ Inserted placeholder charter_id={new_id} reserve={reserve}")
        except Exception as e:
            print(f"❌ Error inserting reserve {reserve}: {e}")
            conn.rollback()

    conn.commit()
    print(f"\n✅ Created {created} placeholders")
    cur.close(); conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
