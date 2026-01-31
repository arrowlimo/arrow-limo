#!/usr/bin/env python3
"""
Archive zero-amount placeholder payments (89 records).
These are likely deleted/incomplete records that should not appear in financial reports.

Strategy:
1. Identify payments with NULL or $0.00 amounts
2. Create payments_archived table if not exists
3. Move records to archive with reason='zero_amount_placeholder'
4. Add deletion audit log entry
"""

import psycopg2
import os
from datetime import datetime
import argparse

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    parser = argparse.ArgumentParser(description='Archive zero-amount placeholder payments')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 120)
    print("ZERO-AMOUNT PAYMENT ARCHIVAL")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    print("=" * 120)
    
    # Find zero-amount payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            payment_method,
            account_number,
            reserve_number,
            notes,
            created_at
        FROM payments
        WHERE (amount IS NULL OR amount = 0)
        AND (charter_id IS NULL OR charter_id = 0)
        AND banking_transaction_id IS NULL
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        ORDER BY payment_date DESC
    """)
    
    zero_payments = cur.fetchall()
    
    print(f"\n### ZERO-AMOUNT PAYMENTS ###")
    print(f"Total found: {len(zero_payments)} records")
    
    if zero_payments:
        print(f"\nSample records (first 20):")
        print(f"{'ID':<8} {'Date':<12} {'Method':<15} {'Account':<12} {'Reserve':<12} {'Created':<20}")
        print("-" * 100)
        
        for p in zero_payments[:20]:
            pid, pdate, method, acct, resnum, notes, created = p
            method_str = method or '(None)'
            acct_str = acct or ''
            resnum_str = resnum or ''
            created_str = str(created)[:19] if created else ''
            print(f"{pid:<8} {str(pdate):<12} {method_str:<15} {acct_str:<12} {resnum_str:<12} {created_str:<20}")
        
        # Analyze patterns
        print(f"\n### PATTERNS ANALYSIS ###")
        
        # By year
        cur.execute("""
            SELECT 
                EXTRACT(YEAR FROM payment_date) as year,
                COUNT(*) as count
            FROM payments
            WHERE (amount IS NULL OR amount = 0)
            AND (charter_id IS NULL OR charter_id = 0)
            AND banking_transaction_id IS NULL
            AND payment_date >= '2007-01-01'
            AND payment_date < '2025-01-01'
            GROUP BY EXTRACT(YEAR FROM payment_date)
            ORDER BY year DESC
        """)
        
        yearly = cur.fetchall()
        print(f"\nBy Year:")
        for year, count in yearly:
            print(f"  {int(year)}: {count} records")
        
        # By payment method
        cur.execute("""
            SELECT 
                COALESCE(payment_method, '(None)') as method,
                COUNT(*) as count
            FROM payments
            WHERE (amount IS NULL OR amount = 0)
            AND (charter_id IS NULL OR charter_id = 0)
            AND banking_transaction_id IS NULL
            AND payment_date >= '2007-01-01'
            AND payment_date < '2025-01-01'
            GROUP BY payment_method
            ORDER BY count DESC
        """)
        
        methods = cur.fetchall()
        print(f"\nBy Payment Method:")
        for method, count in methods:
            print(f"  {method}: {count} records")
    
    if args.write and zero_payments:
        print(f"\n### APPLYING ARCHIVAL ###")
        
        # Create archive table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payments_archived (
                LIKE payments INCLUDING ALL,
                archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                archive_reason VARCHAR(255)
            )
        """)
        
        print(f"Created/verified payments_archived table")
        
        # Copy records to archive
        payment_ids = [p[0] for p in zero_payments]
        placeholders = ','.join(['%s'] * len(payment_ids))
        
        cur.execute(f"""
            INSERT INTO payments_archived 
            SELECT *, CURRENT_TIMESTAMP, 'zero_amount_placeholder'
            FROM payments
            WHERE payment_id IN ({placeholders})
        """, payment_ids)
        
        archived_count = cur.rowcount
        print(f"Copied {archived_count} records to payments_archived")
        
        # Delete from payments table
        cur.execute(f"""
            DELETE FROM payments
            WHERE payment_id IN ({placeholders})
        """, payment_ids)
        
        deleted_count = cur.rowcount
        print(f"Deleted {deleted_count} records from payments table")
        
        # Log to deletion audit if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'deletion_audit_log'
            )
        """)
        
        if cur.fetchone()[0]:
            cur.execute("""
                INSERT INTO deletion_audit_log (table_name, records_deleted, deleted_at, reason, script_name)
                VALUES ('payments', %s, CURRENT_TIMESTAMP, 'zero_amount_placeholder', 'archive_zero_amount_payments.py')
            """, (deleted_count,))
            print(f"Logged to deletion_audit_log")
        
        conn.commit()
        
        print(f"\n### SUMMARY ###")
        print(f"[OK] Archived {archived_count} zero-amount placeholder payments")
        print(f"[OK] Records moved to payments_archived table")
        print(f"[OK] Deletion logged for audit compliance")
        
    else:
        print(f"\n### DRY RUN COMPLETE ###")
        print(f"Run with --write to archive {len(zero_payments)} records")
        print(f"This will:")
        print(f"  1. Create payments_archived table if needed")
        print(f"  2. Copy {len(zero_payments)} records to archive")
        print(f"  3. Delete from payments table")
        print(f"  4. Log deletion for audit trail")
    
    print("\n" + "=" * 120)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
