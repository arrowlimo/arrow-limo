#!/usr/bin/env python3
"""Find and fix NULL payment_key duplicates for all remaining overpaid charters.

Following the Waste Connections pattern, check if other clients have the same
issue: legitimate payments with NULL keys from 2025-08-05 import.

Strategy:
  1. Find all overpaid charters
  2. For each, check if payments exist with NULL key and created_at='2025-08-05'
  3. Cross-reference with LMS to determine if legitimate or duplicate
  4. Delete true duplicates, keep legitimate payments

Usage:
  python scripts/fix_all_null_key_duplicates.py              # Dry-run analysis
  python scripts/fix_all_null_key_duplicates.py --write      # Execute cleanup
"""

import os
import psycopg2
import pyodbc
from argparse import ArgumentParser
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
LMS_PATH = r"L:\limo\backups\lms.mdb"


def pg_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def lms_conn():
    return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};')


def find_null_key_payments_2025_08_05(cur):
    """Find all payments with NULL key created on 2025-08-05 for overpaid charters."""
    cur.execute("""
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.amount,
            p.payment_date,
            c.client_name
        FROM payments p
        JOIN charters ch ON ch.reserve_number = p.reserve_number
        JOIN clients c ON c.client_id = ch.client_id
        WHERE p.payment_key IS NULL
        AND p.created_at::date = '2025-08-05'
        AND ch.paid_amount > ch.total_amount_due
        ORDER BY p.reserve_number, p.payment_date
    """)
    return cur.fetchall()


def check_lms_for_payment(lms_cur, reserve_number, amount, payment_date):
    """Check if payment exists in LMS."""
    lms_cur.execute("""
        SELECT PaymentID, Amount, LastUpdated
        FROM Payment
        WHERE Reserve_No = ?
        AND ABS(Amount - ?) < 0.01
    """, (reserve_number, float(amount)))
    return lms_cur.fetchall()


def analyze(dry_run=True):
    pg = pg_conn()
    pg_cur = pg.cursor()
    lms = lms_conn()
    lms_cur = lms.cursor()
    
    try:
        null_key_payments = find_null_key_payments_2025_08_05(pg_cur)
        print(f"Found {len(null_key_payments)} NULL-key payments from 2025-08-05 in overpaid charters")
        print()
        
        if not null_key_payments:
            print("No NULL-key payments found - all clean!")
            return
        
        # Group by reserve
        by_reserve = {}
        for pid, reserve, amount, pdate, client in null_key_payments:
            if reserve not in by_reserve:
                by_reserve[reserve] = []
            by_reserve[reserve].append((pid, amount, pdate, client))
        
        print(f"Affected reserves: {len(by_reserve)}")
        print()
        
        to_delete = []
        to_keep = []
        
        for reserve, payments in sorted(by_reserve.items()):
            print(f"Reserve {reserve} ({payments[0][3]}):")
            print(f"  {len(payments)} NULL-key payments")
            
            # Check LMS
            lms_payments = check_lms_for_payment(lms_cur, reserve, payments[0][1], payments[0][2])
            print(f"  LMS has {len(lms_payments)} matching payments")
            
            if len(lms_payments) == 0:
                # No LMS payments - all are duplicates
                print(f"  → DELETE all {len(payments)} (no LMS record)")
                to_delete.extend([p[0] for p in payments])
            elif len(lms_payments) == len(payments):
                # Same count - keep all
                print(f"  → KEEP all {len(payments)} (matches LMS count)")
                to_keep.extend([p[0] for p in payments])
            elif len(lms_payments) < len(payments):
                # More payments than LMS - keep LMS count, delete rest
                keep_count = len(lms_payments)
                delete_count = len(payments) - keep_count
                print(f"  → KEEP {keep_count}, DELETE {delete_count} (LMS has fewer)")
                to_keep.extend([p[0] for p in payments[:keep_count]])
                to_delete.extend([p[0] for p in payments[keep_count:]])
            else:
                # More LMS than payments - unusual, keep all
                print(f"  → KEEP all {len(payments)} (LMS has more - investigate)")
                to_keep.extend([p[0] for p in payments])
            print()
        
        print("=" * 70)
        print(f"Summary:")
        print(f"  To DELETE: {len(to_delete)} payments (duplicates)")
        print(f"  To KEEP: {len(to_keep)} payments (legitimate)")
        print()
        
        if dry_run:
            print("=== DRY-RUN MODE ===")
            print("Run with --write to execute deletion")
        else:
            if to_delete:
                # Delete income_ledger entries first (FK constraint)
                pg_cur.execute("DELETE FROM income_ledger WHERE payment_id = ANY(%s)", (to_delete,))
                income_deleted = pg_cur.rowcount
                
                # Delete banking_payment_links (FK constraint)
                pg_cur.execute("DELETE FROM banking_payment_links WHERE payment_id = ANY(%s)", (to_delete,))
                banking_links_deleted = pg_cur.rowcount
                
                # Delete payments
                pg_cur.execute("DELETE FROM payments WHERE payment_id = ANY(%s)", (to_delete,))
                payments_deleted = pg_cur.rowcount
                
                # Recalculate affected charters
                affected = set(by_reserve.keys())
                for reserve in affected:
                    pg_cur.execute("""
                        WITH payment_sum AS (
                            SELECT COALESCE(SUM(amount), 0) as total
                            FROM payments WHERE reserve_number = %s
                        )
                        UPDATE charters
                        SET paid_amount = (SELECT total FROM payment_sum),
                            balance = total_amount_due - (SELECT total FROM payment_sum)
                        WHERE reserve_number = %s
                    """, (reserve, reserve))
                
                pg.commit()
                print(f"✓ Deleted {income_deleted} income_ledger entries")
                print(f"✓ Deleted {banking_links_deleted} banking_payment_links entries")
                print(f"✓ Deleted {payments_deleted} duplicate payments")
                print(f"✓ Updated {len(affected)} charters")
    
    finally:
        pg_cur.close()
        pg.close()
        lms_cur.close()
        lms.close()


def main():
    parser = ArgumentParser(description='Fix NULL payment_key duplicates for all clients')
    parser.add_argument('--write', action='store_true', help='Execute deletion')
    args = parser.parse_args()
    
    analyze(dry_run=not args.write)


if __name__ == '__main__':
    main()
