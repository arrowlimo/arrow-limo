#!/usr/bin/env python3
"""
Rollback the incorrect Scotia Dec 2013 statement import.
Delete the 142 transactions that were just imported incorrectly.
"""

import os
import psycopg2
from datetime import datetime

ACCOUNT = '903990106011'

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    print("\n" + "="*80)
    print("ROLLBACK INCORRECT SCOTIA DECEMBER 2013 IMPORT")
    print("="*80)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Find transactions that were just imported (most recent 142)
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    current_count = cur.fetchone()[0]
    
    print(f"Current December 2013 transactions: {current_count}")
    print(f"Target after rollback: 92 (original QuickBooks reconciliation data)")
    print(f"Will delete: {current_count - 92} transactions")
    
    # Create backup first
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'scotia_dec2013_backup_{timestamp}'
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    
    print(f"\n[BACKUP] Created {backup_table} with {current_count} rows")
    
    # Get the IDs of the original 92 transactions (keep these)
    cur.execute("""
        SELECT transaction_id FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        ORDER BY transaction_id
        LIMIT 92
    """, (ACCOUNT,))
    
    keep_ids = [row[0] for row in cur.fetchall()]
    
    print(f"\nKeeping {len(keep_ids)} original transactions (IDs: {keep_ids[0]} to {keep_ids[-1]})")
    
    # Delete everything else
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
        AND transaction_id NOT IN %s
    """, (ACCOUNT, tuple(keep_ids)))
    
    deleted_count = cur.rowcount
    conn.commit()
    
    print(f"\n[SUCCESS] Deleted {deleted_count} incorrect transactions")
    
    # Verify
    cur.execute("""
        SELECT 
            COUNT(*),
            SUM(debit_amount),
            SUM(credit_amount)
        FROM banking_transactions
        WHERE account_number = %s
        AND transaction_date >= '2013-12-01'
        AND transaction_date <= '2013-12-31'
    """, (ACCOUNT,))
    
    final_count, debits, credits = cur.fetchone()
    
    print(f"\n{'='*80}")
    print("RESTORED STATE")
    print(f"{'='*80}")
    print(f"December 2013 transactions: {final_count}")
    print(f"Total debits: ${float(debits or 0):,.2f}")
    print(f"Total credits: ${float(credits or 0):,.2f}")
    print(f"\n✅ Rollback complete - ready for corrected import")
    
    cur.close()
    conn.close()
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
