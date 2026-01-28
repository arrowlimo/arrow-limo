#!/usr/bin/env python3
"""Recalculate charter.paid_amount and balance from payments using reserve_number.

Follows documented correct pattern:
  paid_amount = SUM(payments.amount WHERE payments.reserve_number = charters.reserve_number)
  balance = total_amount_due - paid_amount

Safety:
  - Dry-run unless --apply
  - Prints number of charters affected and sample changes
  - Uses a CTE for atomic update
"""

import os
import psycopg2
import argparse
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


def preview_changes(cur):
    cur.execute(
        """
        WITH payment_sums AS (
            SELECT reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        ), recompute AS (
            SELECT c.charter_id, c.reserve_number, c.paid_amount AS old_paid, ps.actual_paid AS new_paid,
                   c.total_amount_due, (c.total_amount_due - ps.actual_paid) AS new_balance, c.balance AS old_balance
            FROM charters c
            JOIN payment_sums ps ON ps.reserve_number = c.reserve_number
            WHERE COALESCE(c.paid_amount,0) <> ps.actual_paid
        )
        SELECT COUNT(*), SUM(new_paid - old_paid) FROM recompute
        """
    )
    count, delta = cur.fetchone()
    return count, delta or 0


def apply_update(cur):
    cur.execute(
        """
        WITH payment_sums AS (
            SELECT reserve_number, ROUND(SUM(COALESCE(amount,0))::numeric,2) AS actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = ps.actual_paid,
            balance = c.total_amount_due - ps.actual_paid,
            updated_at = NOW()
        FROM payment_sums ps
        WHERE c.reserve_number = ps.reserve_number
          AND COALESCE(c.paid_amount,0) <> ps.actual_paid
        RETURNING c.charter_id, c.reserve_number, c.paid_amount, c.balance
        """
    )
    return cur.fetchall()


def main():
    parser = argparse.ArgumentParser(description="Recalculate charter paid_amount/balance from payments")
    parser.add_argument('--apply', action='store_true', help='Perform update')
    args = parser.parse_args()
    conn = get_conn()
    cur = conn.cursor()
    count, delta = preview_changes(cur)
    print(f"Charters needing update: {count} | Net paid_amount delta: {delta:,.2f}")
    if not args.apply:
        print("[DRY RUN] No changes applied. Use --apply to update.")
        cur.close(); conn.close(); return
    updated = apply_update(cur)
    conn.commit()
    print(f"Updated {len(updated)} charters.")
    # Show sample
    for row in updated[:20]:
        charter_id, reserve_number, new_paid, new_balance = row
        print(f"  charter_id={charter_id} reserve={reserve_number} paid={new_paid} balance={new_balance}")
    cur.close(); conn.close()


if __name__ == '__main__':
    main()
