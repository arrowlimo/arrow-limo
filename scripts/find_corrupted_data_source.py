#!/usr/bin/env python3
"""
Find the source of corrupted May 2012 banking data
===================================================
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("FINDING SOURCE OF CORRUPTED MAY 2012 DATA")
    print("=" * 100)
    
    # Check if import metadata columns exist
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns
        WHERE table_name = 'banking_transactions'
          AND column_name IN ('import_source', 'import_batch', 'imported_at', 'source_file', 'created_at')
        ORDER BY column_name
    """)
    
    available_cols = [row[0] for row in cur.fetchall()]
    print(f"\nAvailable metadata columns: {available_cols}")
    
    # Build query dynamically
    select_cols = ['transaction_id', 'transaction_date', 'debit_amount', 'credit_amount']
    select_cols.extend(available_cols)
    
    query = f"""
        SELECT {', '.join(select_cols)}
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-05-01' AND '2012-05-31'
          AND account_number = '0228362'
        ORDER BY transaction_id
        LIMIT 20
    """
    
    print(f"\nQuerying May 2012 transactions with available metadata...")
    cur.execute(query)
    
    rows = cur.fetchall()
    print(f"\nFirst 20 transactions:")
    print("-" * 100)
    
    for row in rows:
        print(f"ID {row[0]:6} | {row[1]} | Debit: ${row[2] or 0:>8.2f} | Credit: ${row[3] or 0:>8.2f}", end="")
        if len(row) > 4:
            print(f" | Metadata: {row[4:]}")
        else:
            print()
    
    # Check for patterns in transaction IDs
    print(f"\n\n{'=' * 100}")
    print("TRANSACTION ID ANALYSIS")
    print("=" * 100)
    
    cur.execute("""
        SELECT MIN(transaction_id), MAX(transaction_id), COUNT(*)
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-05-01' AND '2012-05-31'
          AND account_number = '0228362'
    """)
    
    min_id, max_id, count = cur.fetchone()
    print(f"\nMay 2012 transactions:")
    print(f"  ID range: {min_id} to {max_id}")
    print(f"  Count: {count}")
    print(f"  ID gap: {max_id - min_id + 1 - count} missing IDs in range")
    
    # Check nearby transaction IDs to understand import batch
    print(f"\n\n{'=' * 100}")
    print("CHECKING TRANSACTIONS AROUND ID {min_id} (start of May 2012 data)")
    print("=" * 100)
    
    cur.execute(f"""
        SELECT transaction_id, transaction_date, account_number,
               debit_amount, credit_amount, description
        FROM banking_transactions
        WHERE transaction_id BETWEEN {min_id - 10} AND {min_id + 10}
        ORDER BY transaction_id
    """)
    
    print(f"\nTransactions ID {min_id - 10} to {min_id + 10}:")
    for txn_id, date, acct, debit, credit, desc in cur.fetchall():
        desc_str = (desc or 'NULL')[:40]
        print(f"  {txn_id:6} | {date} | Acct: {acct:10} | D: ${debit or 0:>8.2f} | C: ${credit or 0:>8.2f} | {desc_str}")
    
    # Check if there's a pattern of swapped debits/credits
    print(f"\n\n{'=' * 100}")
    print("DEBIT/CREDIT SWAP ANALYSIS")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_txns,
            SUM(CASE WHEN debit_amount > 0 THEN 1 ELSE 0 END) as has_debit,
            SUM(CASE WHEN credit_amount > 0 THEN 1 ELSE 0 END) as has_credit,
            SUM(CASE WHEN debit_amount > 0 AND credit_amount > 0 THEN 1 ELSE 0 END) as has_both,
            SUM(CASE WHEN debit_amount = 0 AND credit_amount = 0 THEN 1 ELSE 0 END) as has_neither
        FROM banking_transactions
        WHERE transaction_date BETWEEN '2012-05-01' AND '2012-05-31'
          AND account_number = '0228362'
    """)
    
    total, has_debit, has_credit, has_both, has_neither = cur.fetchone()
    print(f"\nMay 2012 debit/credit distribution:")
    print(f"  Total transactions: {total}")
    print(f"  Has debit > 0: {has_debit} ({has_debit/total*100:.1f}%)")
    print(f"  Has credit > 0: {has_credit} ({has_credit/total*100:.1f}%)")
    print(f"  Has both > 0: {has_both}")
    print(f"  Has neither (both 0): {has_neither} ({has_neither/total*100:.1f}%)")
    
    if has_debit == 0 or has_debit < has_credit * 0.1:
        print(f"\n[FAIL] CORRUPTION CONFIRMED: {has_debit} debits vs {has_credit} credits")
        print(f"   Normal checking account should have roughly equal debits and credits.")
        print(f"   This data appears to have debit/credit columns swapped or all mapped to credit.")
    
    # Find which import scripts exist
    print(f"\n\n{'=' * 100}")
    print("CHECKING FOR IMPORT SCRIPTS")
    print("=" * 100)
    
    import glob
    import_scripts = glob.glob('l:/limo/scripts/import_*banking*.py') + glob.glob('l:/limo/scripts/import_*cibc*.py')
    
    if import_scripts:
        print(f"\nFound {len(import_scripts)} banking import scripts:")
        for script in import_scripts:
            print(f"  - {os.path.basename(script)}")
    else:
        print(f"\n[WARN] No import scripts found matching pattern import_*banking*.py or import_*cibc*.py")
    
    cur.close()
    conn.close()
    
    print(f"\n\n{'=' * 100}")
    print("🔧 RECOMMENDED ACTIONS:")
    print("=" * 100)
    print(f"""
1. DELETE corrupted May 2012 data:
   DELETE FROM banking_transactions 
   WHERE transaction_id BETWEEN {min_id} AND {max_id}
     AND account_number = '0228362';

2. Locate original CIBC statement CSV/Excel files for May 2012

3. Review import script column mapping:
   - Ensure debit amounts go to debit_amount column
   - Ensure credit amounts go to credit_amount column  
   - Ensure description is not mapped to 'nan' strings

4. Re-import with corrected column mapping

5. Verify totals match statement after re-import
    """)

if __name__ == '__main__':
    main()
