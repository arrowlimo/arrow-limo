#!/usr/bin/env python3
"""Restore the 2 legitimate Waste Connections payments that were incorrectly deleted.

Payments 24722 and 24849 are legitimate LMS payments that got deleted
because they had NULL payment_key and were created on 2025-08-05.

Usage:
  python scripts/restore_waste_legitimate_payments.py --write
"""

import psycopg2
from argparse import ArgumentParser
from dotenv import load_dotenv
import os

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def pg_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def restore_payments(cur, payment_ids):
    """Restore payments from backup table."""
    
    # Get payment details from backup
    cur.execute("""
        SELECT payment_id, account_number, reserve_number, charter_id, client_id,
               amount, payment_key, last_updated, last_updated_by, created_at,
               payment_method, payment_date, check_number, credit_card_last4,
               credit_card_expiry, authorization_code, status
        FROM payments_backup_waste774_20251123_002119
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    
    payments = cur.fetchall()
    
    for p in payments:
        cur.execute("""
            INSERT INTO payments (
                payment_id, account_number, reserve_number, charter_id, client_id,
                amount, payment_key, last_updated, last_updated_by, created_at,
                payment_method, payment_date, check_number, credit_card_last4,
                credit_card_expiry, authorization_code, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, p)
        
        print(f"  Restored payment {p[0]} - Reserve {p[2]} - ${float(p[5]):.2f}")
    
    # Recalculate charter paid_amount for affected reserves
    affected_reserves = [p[2] for p in payments]
    for reserve in affected_reserves:
        cur.execute("""
            WITH payment_sum AS (
                SELECT COALESCE(SUM(amount), 0) as total
                FROM payments
                WHERE reserve_number = %s
            )
            UPDATE charters
            SET paid_amount = (SELECT total FROM payment_sum),
                balance = total_amount_due - (SELECT total FROM payment_sum)
            WHERE reserve_number = %s
        """, (reserve, reserve))
    
    return len(payments)


def main():
    parser = ArgumentParser(description='Restore legitimate Waste Connections payments')
    parser.add_argument('--write', action='store_true', help='Execute restoration')
    args = parser.parse_args()
    
    conn = pg_conn()
    cur = conn.cursor()
    
    try:
        payment_ids = [24722, 24849]
        
        print("Restoring 2 legitimate Waste Connections payments:")
        print("  Payment 24722 - Reserve 019311 - $774.00")
        print("  Payment 24849 - Reserve 019395 - $774.00")
        print()
        
        if args.write:
            restored = restore_payments(cur, payment_ids)
            conn.commit()
            print(f"\n✓ Restored {restored} payments")
            print("✓ Updated charter balances")
        else:
            print("=== DRY-RUN MODE ===")
            print("Run with --write to execute")
    
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    main()
