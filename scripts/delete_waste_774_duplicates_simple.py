#!/usr/bin/env python3
"""Delete duplicate Waste Connections $774 payments imported on 2025-08-05.

Analysis shows these payments have payment_key=NULL and were incorrectly
assigned to various reserves. Only payments with actual LMS keys are legitimate.

Usage:
  python scripts/delete_waste_774_duplicates_simple.py              # Dry-run
  python scripts/delete_waste_774_duplicates_simple.py --write      # Execute
"""

import os
import psycopg2
from datetime import datetime
from argparse import ArgumentParser
from dotenv import load_dotenv

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


def find_duplicate_payments(cur):
    """Find $774 payments with NULL keys created on 2025-08-05."""
    cur.execute("""
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.amount,
            p.payment_date,
            p.created_at,
            c.client_name
        FROM payments p
        JOIN charters ch ON ch.reserve_number = p.reserve_number
        JOIN clients c ON c.client_id = ch.client_id
        WHERE p.payment_key IS NULL
        AND p.created_at::date = '2025-08-05'
        AND ABS(p.amount - 774.00) < 0.01
        AND LOWER(c.client_name) LIKE '%waste connection%'
        ORDER BY p.payment_id
    """)
    return cur.fetchall()


def create_backup(cur):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"payments_backup_waste774_{timestamp}"
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM payments WHERE payment_id IN (SELECT payment_id FROM payments WHERE payment_key IS NULL AND created_at::date = '2025-08-05' AND ABS(amount - 774.00) < 0.01)")
    cur.execute("SELECT COUNT(*) FROM " + backup_name)
    count = cur.fetchone()[0]
    return backup_name, count


def delete_duplicates(cur, payment_ids):
    """Delete duplicate payments and update charter paid_amount."""
    
    # Get affected charters
    cur.execute("""
        SELECT DISTINCT reserve_number
        FROM payments
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    affected_reserves = [r[0] for r in cur.fetchall()]
    
    # Delete from income_ledger first (foreign key constraint)
    cur.execute("""
        DELETE FROM income_ledger
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    income_deleted = cur.rowcount
    
    # Delete payments
    cur.execute("""
        DELETE FROM payments
        WHERE payment_id = ANY(%s)
    """, (payment_ids,))
    deleted_count = cur.rowcount
    
    # Recalculate paid_amount for affected charters
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
    
    return deleted_count, len(affected_reserves), income_deleted


def delete_false_credits(cur):
    """Delete credit ledger entries for Waste Connections UNIFORM_INSTALLMENT."""
    cur.execute("""
        DELETE FROM charter_credit_ledger
        WHERE client_id IN (SELECT client_id FROM clients WHERE LOWER(client_name) LIKE '%waste connection%')
        AND credit_reason = 'UNIFORM_INSTALLMENT'
        RETURNING credit_id, source_reserve_number, credit_amount
    """)
    deleted_credits = cur.fetchall()
    return deleted_credits


def main():
    parser = ArgumentParser(description='Delete duplicate Waste Connections $774 payments')
    parser.add_argument('--write', action='store_true', help='Execute deletion (default is dry-run)')
    args = parser.parse_args()
    
    conn = pg_conn()
    cur = conn.cursor()
    
    try:
        # Find duplicates
        duplicates = find_duplicate_payments(cur)
        
        if not duplicates:
            print("No duplicate payments found")
            return
        
        print(f"Found {len(duplicates)} duplicate $774 payments (NULL key, created 2025-08-05)")
        print("\nFirst 10:")
        for i, (pid, reserve, amt, pdate, created, client) in enumerate(duplicates[:10], 1):
            print(f"  {i}. Payment {pid} - Reserve {reserve} - ${amt:.2f} on {pdate}")
        if len(duplicates) > 10:
            print(f"  ... and {len(duplicates) - 10} more")
        
        total_amount = sum(d[2] for d in duplicates)
        print(f"\nTotal duplicate amount: ${total_amount:,.2f}")
        
        if args.write:
            # Create backup
            backup_name, backup_count = create_backup(cur)
            print(f"\nBackup created: {backup_name} ({backup_count} rows)")
            
            # Delete false credits first
            deleted_credits = delete_false_credits(cur)
            print(f"\nDeleted {len(deleted_credits)} false credit entries:")
            for credit_id, reserve, amount in deleted_credits[:5]:
                print(f"  Credit {credit_id} - Reserve {reserve} - ${amount:.2f}")
            if len(deleted_credits) > 5:
                print(f"  ... and {len(deleted_credits) - 5} more")
            
            # Delete duplicate payments
            payment_ids = [d[0] for d in duplicates]
            deleted_count, affected_charters, income_deleted = delete_duplicates(cur, payment_ids)
            
            conn.commit()
            
            print(f"\n✓ Deleted {income_deleted} income_ledger entries")
            print(f"✓ Deleted {deleted_count} duplicate payments")
            print(f"✓ Updated {affected_charters} charters")
            print(f"✓ Backup: {backup_name}")
        else:
            print("\n=== DRY-RUN MODE ===")
            print("Would delete these payments and false credits")
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
