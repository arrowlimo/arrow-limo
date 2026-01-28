#!/usr/bin/env python
"""
Create placeholder charters for missing reserve_numbers so charges can attach.
If a placeholder already exists, skip.
"""
import os
import sys
import psycopg2
from datetime import datetime, UTC

MISSING_RESERVES = [
    '015901','015902','012861','016011','016021','016009','016010','016022'
]

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

def main():
    # Hard guard: respect no-LMS-sync policy
    if os.getenv('DISABLE_LMS_SYNC') == '1' or os.path.exists(r"L:\limo\CONFIG_NO_LMS_SYNC.txt"):
        print("❌ LMS sync disabled: skipping create_placeholder_charters.py")
        sys.exit(0)

    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    created = 0
    skipped = 0
    for res in MISSING_RESERVES:
        cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (res,))
        row = cur.fetchone()
        if row:
            skipped += 1
            continue
        now = datetime.now(UTC)
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
                res,
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
        print(f"Inserted placeholder charter_id={new_id} reserve={res}")
    conn.commit()
    print(f"Created {created}, skipped {skipped}")
    cur.close(); conn.close()

if __name__ == '__main__':
    main()
