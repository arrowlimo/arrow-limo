#!/usr/bin/env python3
"""Analyze which types of banking transactions are missing receipts."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 80)
print("BANKING TRANSACTIONS WITHOUT RECEIPTS - BREAKDOWN BY TYPE")
print("=" * 80)

# Check if missing receipts are debits or credits
cur.execute("""
    SELECT 
        bt.account_number,
        CASE 
            WHEN bt.debit_amount IS NOT NULL AND bt.debit_amount > 0 THEN 'DEBIT (Money Out)'
            WHEN bt.credit_amount IS NOT NULL AND bt.credit_amount > 0 THEN 'CREDIT (Money In)'
            ELSE 'ZERO'
        END as transaction_type,
        COUNT(*) as count,
        SUM(COALESCE(bt.debit_amount, bt.credit_amount)) as total_amount
    FROM banking_transactions bt
    WHERE bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id 
        FROM receipts 
        WHERE banking_transaction_id IS NOT NULL
    )
    AND bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id
        FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id IS NOT NULL
    )
    GROUP BY bt.account_number, transaction_type
    ORDER BY bt.account_number, transaction_type
""")

results = cur.fetchall()
print("\nAccount         | Type                  | Count    | Total Amount")
print("-" * 80)
for account, txn_type, count, amount in results:
    print(f"{account:15s} | {txn_type:20s} | {count:8,d} | ${amount:13,.2f}")

# Sample of missing receipts
print("\n" + "=" * 80)
print("SAMPLE TRANSACTIONS WITHOUT RECEIPTS (10 debits, 10 credits)")
print("=" * 80)

print("\n📤 DEBIT TRANSACTIONS (Money Out) without receipts:")
print("-" * 80)
cur.execute("""
    SELECT 
        bt.transaction_date,
        bt.account_number,
        bt.description,
        bt.debit_amount
    FROM banking_transactions bt
    WHERE bt.debit_amount IS NOT NULL 
      AND bt.debit_amount > 0
      AND bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id 
        FROM receipts 
        WHERE banking_transaction_id IS NOT NULL
    )
    AND bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id
        FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id IS NOT NULL
    )
    ORDER BY bt.transaction_date DESC
    LIMIT 10
""")

for date, account, description, amount in cur.fetchall():
    print(f"{date} | {account:10s} | ${amount:10.2f} | {description[:60]}")

print("\n📥 CREDIT TRANSACTIONS (Money In) without receipts:")
print("-" * 80)
cur.execute("""
    SELECT 
        bt.transaction_date,
        bt.account_number,
        bt.description,
        bt.credit_amount
    FROM banking_transactions bt
    WHERE bt.credit_amount IS NOT NULL 
      AND bt.credit_amount > 0
      AND bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id 
        FROM receipts 
        WHERE banking_transaction_id IS NOT NULL
    )
    AND bt.transaction_id NOT IN (
        SELECT DISTINCT banking_transaction_id
        FROM banking_receipt_matching_ledger
        WHERE banking_transaction_id IS NOT NULL
    )
    ORDER BY bt.transaction_date DESC
    LIMIT 10
""")

for date, account, description, amount in cur.fetchall():
    print(f"{date} | {account:10s} | ${amount:10.2f} | {description[:60]}")

print("\n" + "=" * 80)

cur.close()
conn.close()
