#!/usr/bin/env python3
"""Import orphaned e-transfer email events as payment rows.

Definition of orphaned e-transfer email event:
  - source='outlook_etransfer_payment'
  - matched_account_number (reserve_number) NOT NULL
  - amount NOT NULL
  - No existing payment row where (reserve_number, amount, payment_date) match
    (payment_date taken as DATE(email_date))
    OR tolerance match (within $0.01) – we treat exact cents only to avoid drifting.

Safety Measures:
  - Dry-run by default (no changes) unless --write
  - Duplicate prevention via WHERE NOT EXISTS composite business key check
  - Deterministic payment_key: 'ETR:{email_event_id}' ensuring idempotency
  - Prints summary before committing

Post-Import Recommendation:
  - Run recalc script to update charter.paid_amount and charter.balance using reserve_number sums

Payment Method:
  - Use 'bank_transfer' (already whitelisted) for Interac e-transfer receipts

"""

import os
import psycopg2
import argparse
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def fetch_orphans(cur):
    """Return orphaned e-transfer email events eligible for payment creation."""
    cur.execute(
        """
        WITH et AS (
            SELECT id, matched_account_number AS reserve_number, amount, email_date
            FROM email_financial_events
            WHERE source='outlook_etransfer_payment'
              AND matched_account_number IS NOT NULL
              AND amount IS NOT NULL
        )
        SELECT et.id, et.reserve_number, et.amount, et.email_date::date AS payment_date
        FROM et
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p
            WHERE p.reserve_number = et.reserve_number
              AND p.amount = et.amount
              AND p.payment_date = et.email_date::date
        )
        ORDER BY et.email_date
        """
    )
    return cur.fetchall()


def import_orphans(write: bool):
    conn = get_conn()
    cur = conn.cursor()
    orphans = fetch_orphans(cur)
    total_amount = sum(row[2] for row in orphans)
    print("=== Orphaned E-Transfer Email Events ===")
    print(f"Count: {len(orphans)}  Total: ${total_amount:,.2f}")
    if not write:
        print("\n[DRY RUN] No inserts performed. Use --write to apply.")
        # Show sample first 15
        for row in orphans[:15]:
            print(f"  email_event_id={row[0]} reserve={row[1]} amount=${row[2]:.2f} date={row[3]}")
        cur.close(); conn.close(); return

    inserted = 0
    for email_event_id, reserve_number, amount, payment_date in orphans:
        payment_key = f"ETR:{email_event_id}"  # deterministic/idempotent
        # Insert with protection; use ON CONFLICT DO NOTHING if a unique constraint exists later
        cur.execute(
            """
            INSERT INTO payments (
                reserve_number, amount, payment_key, payment_method, payment_date, created_at, updated_at
            )
            SELECT %s, %s, %s, 'bank_transfer', %s, NOW(), NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM payments p
                WHERE p.reserve_number=%s AND p.amount=%s AND p.payment_date=%s
            )
            """,
            (reserve_number, amount, payment_key, payment_date, reserve_number, amount, payment_date)
        )
        if cur.rowcount:
            inserted += 1
    conn.commit()
    print(f"Inserted payments: {inserted}")
    skipped = len(orphans) - inserted
    print(f"Skipped (already existed during race/double run): {skipped}")
    cur.close(); conn.close()


def main():
    parser = argparse.ArgumentParser(description="Import orphaned e-transfer email events as payments")
    parser.add_argument('--write', action='store_true', help='Perform inserts')
    args = parser.parse_args()
    import_orphans(write=args.write)


if __name__ == '__main__':
    main()
