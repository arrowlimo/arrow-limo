#!/usr/bin/env python3
"""Analyze linkage potential of imported email events to payments and charters.

After importing confirmation and e-transfer emails into email_financial_events,
assess how many can be linked to existing records via:
  - reserve_number + amount (fuzzy tolerance)
  - reserve_number + date proximity
  - reserve_number alone (for reference)

Reports:
  1. E-transfer events with valid reserve + amount matching existing payments
  2. Confirmation events with deposit amount matching payment patterns
  3. Orphaned email events (reserve exists but no matching payment yet)
  4. Unmatched payments that might match newly imported email events

Safe analysis only (no DB writes).
"""

import os
import psycopg2
from decimal import Decimal
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


def main():
    conn = get_conn()
    cur = conn.cursor()

    # Count imported email events
    cur.execute("""
        SELECT source, COUNT(*), COUNT(CASE WHEN amount IS NOT NULL THEN 1 END),
               COUNT(CASE WHEN matched_account_number IS NOT NULL THEN 1 END)
        FROM email_financial_events
        WHERE source IN ('outlook_etransfer_payment', 'outlook_charter_confirmation')
        GROUP BY source
    """)
    print("=== Imported Email Events Summary ===")
    for row in cur.fetchall():
        src, total, with_amt, with_reserve = row
        print(f"{src}:")
        print(f"  Total: {total}")
        print(f"  With amount: {with_amt}")
        print(f"  With reserve_number: {with_reserve}")

    # E-transfer events with reserve + amount
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM email_financial_events
        WHERE source = 'outlook_etransfer_payment'
          AND matched_account_number IS NOT NULL
          AND amount IS NOT NULL
    """)
    etransfer_count, etransfer_sum = cur.fetchone()
    print(f"\nE-transfer events (reserve + amount): {etransfer_count} totaling ${etransfer_sum or 0:,.2f}")

    # Confirmation events with deposit amount
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM email_financial_events
        WHERE source = 'outlook_charter_confirmation'
          AND amount IS NOT NULL
    """)
    conf_count, conf_sum = cur.fetchone()
    print(f"Confirmation events (deposit amount): {conf_count} totaling ${conf_sum or 0:,.2f}")

    # Match analysis: e-transfer → payments (exact reserve + amount within 5%)
    print("\n=== E-Transfer → Payment Matching Analysis ===")
    cur.execute("""
        WITH etransfer_events AS (
            SELECT id, matched_account_number as reserve_number, amount, email_date
            FROM email_financial_events
            WHERE source = 'outlook_etransfer_payment'
              AND matched_account_number IS NOT NULL
              AND amount IS NOT NULL
        )
        SELECT COUNT(DISTINCT e.id) as matched_events,
               COUNT(DISTINCT p.payment_id) as matched_payments,
               SUM(e.amount) as email_total,
               SUM(p.amount) as payment_total
        FROM etransfer_events e
        JOIN payments p ON p.reserve_number = e.reserve_number
        WHERE ABS(e.amount - p.amount) / NULLIF(p.amount, 0) < 0.05
          OR ABS(e.amount - p.amount) < 1.0
    """)
    row = cur.fetchone()
    if row and row[0]:
        print(f"E-transfer events matching existing payments: {row[0]}")
        print(f"Matched payments: {row[1]}")
        print(f"Email total: ${row[2] or 0:,.2f}")
        print(f"Payment total: ${row[3] or 0:,.2f}")
    else:
        print("No e-transfer events matched to payments via amount tolerance.")

    # Confirmation deposits → payments
    print("\n=== Confirmation Deposit → Payment Matching Analysis ===")
    cur.execute("""
        WITH conf_deposits AS (
            SELECT id, matched_account_number as reserve_number, amount as deposit, email_date
            FROM email_financial_events
            WHERE source = 'outlook_charter_confirmation'
              AND matched_account_number IS NOT NULL
              AND amount IS NOT NULL
        )
        SELECT COUNT(DISTINCT c.id) as matched_events,
               COUNT(DISTINCT p.payment_id) as matched_payments,
               SUM(c.deposit) as email_total,
               SUM(p.amount) as payment_total
        FROM conf_deposits c
        JOIN payments p ON p.reserve_number = c.reserve_number
        WHERE ABS(c.deposit - p.amount) / NULLIF(p.amount, 0) < 0.05
          OR ABS(c.deposit - p.amount) < 1.0
    """)
    row = cur.fetchone()
    if row and row[0]:
        print(f"Confirmation deposits matching existing payments: {row[0]}")
        print(f"Matched payments: {row[1]}")
        print(f"Email total: ${row[2] or 0:,.2f}")
        print(f"Payment total: ${row[3] or 0:,.2f}")
    else:
        print("No confirmation deposits matched to payments via amount tolerance.")

    # Orphaned e-transfer events (reserve valid but no payment match)
    print("\n=== Orphaned E-Transfer Events (No Payment Match) ===")
    cur.execute("""
        WITH etransfer_events AS (
            SELECT id, matched_account_number as reserve_number, amount, email_date
            FROM email_financial_events
            WHERE source = 'outlook_etransfer_payment'
              AND matched_account_number IS NOT NULL
              AND amount IS NOT NULL
        )
        SELECT COUNT(*), SUM(e.amount)
        FROM etransfer_events e
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p
            WHERE p.reserve_number = e.reserve_number
              AND (ABS(e.amount - p.amount) / NULLIF(p.amount, 0) < 0.05
                   OR ABS(e.amount - p.amount) < 1.0)
        )
    """)
    orphan_count, orphan_sum = cur.fetchone()
    print(f"Orphaned e-transfer events: {orphan_count or 0} totaling ${orphan_sum or 0:,.2f}")
    print("(These may represent NEW payments not yet in payments table)")

    # Top orphaned reserves
    cur.execute("""
        WITH etransfer_events AS (
            SELECT id, matched_account_number as reserve_number, amount, email_date
            FROM email_financial_events
            WHERE source = 'outlook_etransfer_payment'
              AND matched_account_number IS NOT NULL
              AND amount IS NOT NULL
        )
        SELECT e.reserve_number, COUNT(*) as event_count, SUM(e.amount) as total_amount
        FROM etransfer_events e
        WHERE NOT EXISTS (
            SELECT 1 FROM payments p
            WHERE p.reserve_number = e.reserve_number
              AND (ABS(e.amount - p.amount) / NULLIF(p.amount, 0) < 0.05
                   OR ABS(e.amount - p.amount) < 1.0)
        )
        GROUP BY e.reserve_number
        ORDER BY total_amount DESC
        LIMIT 15
    """)
    print("\nTop orphaned reserves (by total amount):")
    for reserve, count, total in cur.fetchall():
        print(f"  {reserve}: {count} events, ${total:,.2f}")

    # Unmatched payments that might link to email events
    print("\n=== Unmatched Payments → Email Event Linkage Potential ===")
    cur.execute("""
        WITH unmatched_payments AS (
            SELECT payment_id, reserve_number, amount, payment_date
            FROM payments
            WHERE reserve_number IS NOT NULL
              AND reserve_number NOT IN (SELECT DISTINCT reserve_number FROM charters WHERE reserve_number IS NOT NULL)
        ),
        email_reserves AS (
            SELECT DISTINCT matched_account_number as reserve_number
            FROM email_financial_events
            WHERE matched_account_number IS NOT NULL
        )
        SELECT COUNT(*), SUM(p.amount)
        FROM unmatched_payments p
        JOIN email_reserves e ON e.reserve_number = p.reserve_number
    """)
    unmatched_with_email = cur.fetchone()
    print(f"Unmatched payments with email event reserve: {unmatched_with_email[0] or 0} totaling ${unmatched_with_email[1] or 0:,.2f}")

    cur.close()
    conn.close()

    print("\n=== Next Steps ===")
    print("1. Create payment records for orphaned e-transfer events (new deposits)")
    print("2. Link existing payments to email events via reserve_number + amount")
    print("3. Recalculate charter.paid_amount using reserve_number sums")
    print("4. Verify charter.balance = total_amount_due - paid_amount")


if __name__ == '__main__':
    main()
