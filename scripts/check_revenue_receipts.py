#!/usr/bin/env python3
"""Check if receipts exist for deposit/credit transactions using revenue column."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 80)
print("RECEIPTS WITH REVENUE COLUMN (deposits/income)")
print("=" * 80)

cur.execute("""
    SELECT 
        CASE 
            WHEN revenue > 0 THEN 'REVENUE/DEPOSIT'
            WHEN expense > 0 THEN 'EXPENSE'
            ELSE 'NEITHER'
        END as receipt_type,
        COUNT(*) as count,
        SUM(gross_amount) as total_amount
    FROM receipts
    WHERE created_from_banking = true
    GROUP BY receipt_type
    ORDER BY receipt_type
""")

for rtype, count, amount in cur.fetchall():
    print(f"{rtype:20s} | {count:8,d} receipts | ${amount:15,.2f}")

# Check coverage by transaction type
print("\n" + "=" * 80)
print("BANKING TRANSACTION COVERAGE (with receipts)")
print("=" * 80)

cur.execute("""
    SELECT 
        bt.account_number,
        CASE 
            WHEN bt.debit_amount > 0 THEN 'DEBIT (Money Out)'
            WHEN bt.credit_amount > 0 THEN 'CREDIT (Money In)'
            ELSE 'ZERO'
        END as txn_type,
        COUNT(*) as total_count,
        COUNT(r.receipt_id) as with_receipt,
        COUNT(*) - COUNT(r.receipt_id) as missing
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    GROUP BY bt.account_number, txn_type
    ORDER BY bt.account_number, txn_type
""")

print("\nAccount              | Type                | Total  | With Receipt | Missing")
print("-" * 85)
for account, txn_type, total, with_receipt, missing in cur.fetchall():
    pct = (with_receipt / total * 100) if total > 0 else 0
    icon = "✓" if missing == 0 else "⚠️"
    print(f"{icon} {account:17s} | {txn_type:18s} | {total:6,d} | {with_receipt:12,d} | {missing:7,d} ({pct:.1f}%)")

# Sample of credit transactions with and without receipts
print("\n" + "=" * 80)
print("SAMPLE CREDIT TRANSACTIONS (Money In)")
print("=" * 80)

print("\n✓ WITH RECEIPTS:")
cur.execute("""
    SELECT 
        bt.transaction_date,
        bt.description,
        bt.credit_amount,
        r.vendor_name,
        r.gl_account_name
    FROM banking_transactions bt
    JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0
    ORDER BY bt.transaction_date DESC
    LIMIT 5
""")

for date, desc, amount, vendor, gl in cur.fetchall():
    print(f"  {date} | ${amount:10.2f} | {vendor:30s} | {gl or 'NO GL'}")

print("\n⚠️  WITHOUT RECEIPTS:")
cur.execute("""
    SELECT 
        bt.transaction_date,
        bt.account_number,
        bt.description,
        bt.credit_amount
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.credit_amount > 0
      AND r.receipt_id IS NULL
    ORDER BY bt.transaction_date DESC
    LIMIT 5
""")

for date, account, desc, amount in cur.fetchall():
    print(f"  {date} | {account:12s} | ${amount:10.2f} | {desc[:50]}")

print("\n" + "=" * 80)

cur.close()
conn.close()
