#!/usr/bin/env python3
"""Verify if E-TRANSFER NETWORK FEE entries were imported and are in the database."""

import psycopg2
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()
conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    database=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("="*80)
print("VERIFICATION: E-TRANSFER NETWORK FEE entries")
print("="*80)

# Check E-TRANSFER NETWORK FEE entries in receipts
cur.execute("""
    SELECT 
        r.receipt_id, r.receipt_date, r.gross_amount, r.description, r.expense_account,
        bt.account_number, bt.transaction_date, r.banking_transaction_id
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.description LIKE '%E-TRANSFER%NETWORK%' OR r.description LIKE '%ETRANSFER%FEE%'
    ORDER BY r.receipt_date DESC
    LIMIT 20
""")

rows = cur.fetchall()
print(f"\nE-TRANSFER NETWORK FEE entries in receipts table: {len(rows)} found")
print()
for row in rows:
    print(f"  Receipt ID: {row[0]}")
    print(f"  Receipt Date: {row[1]}")
    print(f"  Amount: ${row[2]}")
    print(f"  Description: {row[3]}")
    print(f"  Expense Account: {row[4]}")
    if row[5]:
        print(f"  ✅ LINKED TO BANKING: Account {row[5]}, Transaction {row[7]}")
    else:
        print(f"  ⚠️  NOT linked to banking")
    print()

# Also check all receipts on 2025-12-31 with amounts matching common CIBC fees
print("="*80)
print("All RECEIPTS on 2025-12-31 (end of month recurring fee check):")
cur.execute("""
    SELECT 
        r.receipt_id, r.receipt_date, r.gross_amount, r.description, r.expense_account,
        bt.account_number, r.banking_transaction_id
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE DATE(r.receipt_date) = '2025-12-31'
    ORDER BY r.gross_amount DESC
""")

rows = cur.fetchall()
print(f"Total receipts on 2025-12-31: {len(rows)}\n")
for row in rows[:20]:  # Show first 20
    acct = f"(acct {row[5]})" if row[5] else "(no link)"
    banking_id = f"[banking_txn: {row[6]}]" if row[6] else ""
    print(f"  ${row[2]:>8.2f} | {row[3]:<40} {acct} {banking_id}")

# Now check BANKING_TRANSACTIONS directly from CIBC import to confirm they're there
print("\n" + "="*80)
print("ALL BANKING TRANSACTIONS on 2025-12-31 (what CIBC import created):")
cur.execute("""
    SELECT 
        bt.transaction_id, bt.account_number, bt.transaction_date, 
        bt.description, bt.debit_amount, bt.credit_amount, bt.receipt_id, bt.created_at
    FROM banking_transactions bt
    WHERE DATE(bt.transaction_date) = '2025-12-31'
    ORDER BY COALESCE(bt.debit_amount, 0) DESC
""")

rows = cur.fetchall()
print(f"Total banking transactions on 2025-12-31: {len(rows)}\n")
for row in rows:
    txn_id = row[0]
    acct = row[1]
    amount = row[4] or row[5]
    desc = row[3]
    receipt_id = row[6]
    created = row[7]
    has_receipt = "✅ HAS RECEIPT" if receipt_id else "⚠️ NO RECEIPT"
    print(f"  ${amount:>8.2f} | {desc:<40} | Acct: {acct} | {has_receipt}")

print("\n" + "="*80)
print("SUMMARY:")
print("="*80)
print("✅ If receipts appear above with banking_transaction_id set: IMPORTED and LINKED")
print("✅ If banking_transactions appear above: IMPORTED from CIBC")
print("⚠️  Deduplication only prevented DOUBLE imports (same transaction twice)")
print("⚠️  Legitimate recurring fees SHOULD be imported once and appear here")

cur.close()
conn.close()
