#!/usr/bin/env python3
"""Check receipts table for deposit column and deposit receipts."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Check for deposit column
print("=" * 80)
print("RECEIPTS TABLE COLUMNS (deposit-related)")
print("=" * 80)
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND (column_name LIKE '%deposit%' OR column_name LIKE '%credit%' OR column_name LIKE '%debit%')
    ORDER BY ordinal_position
""")

cols = cur.fetchall()
for col, dtype in cols:
    print(f"  {col}: {dtype}")

# Check receipts with deposit flag
print("\n" + "=" * 80)
print("RECEIPTS BY TYPE (expense vs deposit)")
print("=" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN is_deposit = true THEN 'DEPOSIT (Money In)'
            ELSE 'EXPENSE (Money Out)'
        END as receipt_type,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE created_from_banking = true
    GROUP BY is_deposit
    ORDER BY is_deposit
""")

for rtype, count, amount in cur.fetchall():
    print(f"{rtype:25s} | {count:8,d} receipts | ${amount:15,.2f}")

# Now check banking transaction coverage including deposits
print("\n" + "=" * 80)
print("BANKING TRANSACTIONS WITH RECEIPTS (including deposit receipts)")
print("=" * 80)

cur.execute("""
    SELECT 
        bt.account_number,
        CASE 
            WHEN bt.debit_amount > 0 THEN 'DEBIT (Money Out)'
            ELSE 'CREDIT (Money In)'
        END as txn_type,
        COUNT(*) as total_count,
        COUNT(r.receipt_id) as with_receipt_count,
        COUNT(*) - COUNT(r.receipt_id) as missing_receipt_count
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    GROUP BY bt.account_number, txn_type
    ORDER BY bt.account_number, txn_type
""")

print("\nAccount         | Type                | Total | With Receipt | Missing")
print("-" * 80)
for account, txn_type, total, with_receipt, missing in cur.fetchall():
    icon = "✓" if missing == 0 else "⚠️"
    print(f"{icon} {account:12s} | {txn_type:18s} | {total:6,d} | {with_receipt:12,d} | {missing:7,d}")

cur.close()
conn.close()
