#!/usr/bin/env python3
"""
Promote cibc_ledger_staging (53 rows) and cibc_qbo_staging (1,182 rows) 
to banking_transactions table.
"""

import psycopg2
import os
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("CIBC STAGING PROMOTION TO banking_transactions")
print("=" * 80)

# 1. Promote cibc_ledger_staging (53 rows)
print("\n1. Promoting cibc_ledger_staging (53 rows)")
print("-" * 80)

cur.execute("""
    INSERT INTO banking_transactions (
        account_number,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        vendor_extracted,
        category,
        created_at
    )
    SELECT 
        '0228362',  -- CIBC checking account
        txn_date,
        description || ' (from ledger staging)',
        CASE WHEN txn_type = 'Withdrawal' THEN amount ELSE NULL END,
        CASE WHEN txn_type = 'Deposit' THEN amount ELSE NULL END,
        CASE 
            WHEN description LIKE '%Customer Deposit%' THEN 'Customer'
            WHEN description LIKE '%Business Expense%' THEN 'Business Expense'
            ELSE NULL
        END,
        CASE 
            WHEN txn_type = 'Deposit' THEN 'Income'
            WHEN txn_type = 'Withdrawal' THEN 'Expense'
            ELSE NULL
        END,
        NOW()
    FROM cibc_ledger_staging
    WHERE NOT EXISTS (
        SELECT 1 FROM banking_transactions bt
        WHERE bt.transaction_date = cibc_ledger_staging.txn_date
        AND COALESCE(bt.debit_amount, bt.credit_amount) = cibc_ledger_staging.amount
    )
""")

ledger_inserted = cur.rowcount
conn.commit()
print(f"Inserted: {ledger_inserted} rows")

# 2. Promote cibc_qbo_staging (1,182 rows)
print("\n2. Promoting cibc_qbo_staging (1,182 rows)")
print("-" * 80)

cur.execute("""
    INSERT INTO banking_transactions (
        account_number,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        vendor_extracted,
        category,
        created_at
    )
    SELECT 
        '0228362',  -- CIBC checking account
        dtposted,
        COALESCE(memo, name, trntype) || ' (from QBO staging)',
        CASE WHEN trnamt < 0 THEN ABS(trnamt) ELSE NULL END,
        CASE WHEN trnamt > 0 THEN trnamt ELSE NULL END,
        name,
        CASE 
            WHEN trntype = 'CREDIT' THEN 'Income'
            WHEN trntype = 'DEBIT' THEN 'Expense'
            ELSE NULL
        END,
        NOW()
    FROM cibc_qbo_staging
    WHERE NOT EXISTS (
        SELECT 1 FROM banking_transactions bt
        WHERE bt.transaction_date = cibc_qbo_staging.dtposted
        AND (
            (trnamt < 0 AND bt.debit_amount = ABS(trnamt))
            OR
            (trnamt > 0 AND bt.credit_amount = trnamt)
        )
    )
""")

qbo_inserted = cur.rowcount
conn.commit()
print(f"Inserted: {qbo_inserted} rows")

# 3. Verify
print("\n3. VERIFICATION")
print("-" * 80)

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE description LIKE '%(from ledger staging)%'
""")
ledger_verify = cur.fetchone()[0]

cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE description LIKE '%(from QBO staging)%'
""")
qbo_verify = cur.fetchone()[0]

print(f"Ledger staging in banking_transactions: {ledger_verify}")
print(f"QBO staging in banking_transactions: {qbo_verify}")

# 4. Summary
print("\n" + "=" * 80)
print("PROMOTION COMPLETE")
print("=" * 80)

total_inserted = ledger_inserted + qbo_inserted
print(f"\nTotal rows promoted: {total_inserted}")
print(f"  - cibc_ledger_staging: {ledger_inserted}")
print(f"  - cibc_qbo_staging: {qbo_inserted}")

if total_inserted > 0:
    print("\n✓ SUCCESS - Banking transactions updated with historical CIBC data")
else:
    print("\n⚠ WARNING - No rows inserted (may already exist)")

cur.close()
conn.close()
