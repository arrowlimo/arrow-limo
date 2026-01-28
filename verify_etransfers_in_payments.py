#!/usr/bin/env python3
"""Verify if matched e-transfers are already in payments table."""
import psycopg2
import os
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "=" * 140)
print("VERIFY: ARE E-TRANSFERS ALREADY RECORDED AS CHARTER PAYMENTS?".center(140))
print("=" * 140)

# Check unmatched e-transfers in banking_transactions
cur.execute('''
    SELECT COUNT(*) as count, SUM(bt.credit_amount) as total
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NULL;
''')

unmatched_banking = cur.fetchone()
print(f"\n1️⃣ UNMATCHED E-TRANSFERS in banking_transactions:")
print(f"   Count: {unmatched_banking[0]}")
print(f"   Total Amount: ${unmatched_banking[1]:,.2f}")

# Check e-transfers that ARE matched in banking_transactions
cur.execute('''
    SELECT COUNT(*) as count, SUM(bt.credit_amount) as total
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NOT NULL;
''')

matched_banking = cur.fetchone()
print(f"\n2️⃣ MATCHED E-TRANSFERS in banking_transactions:")
print(f"   Count: {matched_banking[0]}")
print(f"   Total Amount: ${matched_banking[1] if matched_banking[1] else 0:,.2f}")

# Check total e-transfers in banking
cur.execute('''
    SELECT COUNT(*) as count, SUM(bt.credit_amount) as total
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%');
''')

total_banking = cur.fetchone()
print(f"\n3️⃣ TOTAL E-TRANSFERS in banking_transactions:")
print(f"   Count: {total_banking[0]}")
print(f"   Total Amount: ${total_banking[1]:,.2f}")

# Now check: do payments exist that could be from e-transfers?
cur.execute('''
    SELECT 
        COUNT(*) as count,
        SUM(p.amount) as total,
        COUNT(DISTINCT p.reserve_number) as unique_reserves,
        COUNT(p.payment_id) FILTER (WHERE p.payment_method ILIKE '%etransfer%' OR p.payment_method ILIKE '%etr%') as etransfer_method_count
    FROM payments p
    WHERE p.payment_date IS NOT NULL;
''')

all_payments = cur.fetchone()
print(f"\n4️⃣ ALL PAYMENTS in payments table:")
print(f"   Count: {all_payments[0]}")
print(f"   Total Amount: ${all_payments[1] if all_payments[1] else 0:,.2f}")
print(f"   Unique Charters: {all_payments[2]}")
print(f"   Marked as e-transfer: {all_payments[3] if all_payments[3] else 0}")

# Check payments that might correspond to e-transfer amounts
# Look for payments with matching amounts within 1 day of banking e-transfer
cur.execute('''
    SELECT 
        COUNT(DISTINCT p.payment_id) as payment_count,
        SUM(p.amount) as payment_total,
        COUNT(DISTINCT bt.transaction_id) as etransfer_count,
        SUM(bt.credit_amount) as etransfer_total
    FROM payments p
    INNER JOIN banking_transactions bt ON 
        ABS(p.amount - bt.credit_amount) < 0.01
        AND (p.payment_date::date = bt.transaction_date::date 
             OR p.payment_date::date = bt.transaction_date::date - interval '1 day'
             OR p.payment_date::date = bt.transaction_date::date + interval '1 day')
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%');
''')

matched_by_amount = cur.fetchone()
print(f"\n5️⃣ PAYMENTS MATCHED BY AMOUNT to E-TRANSFERS:")
print(f"   Payment Count: {matched_by_amount[0] if matched_by_amount[0] else 0}")
print(f"   Payment Total: ${matched_by_amount[1] if matched_by_amount[1] else 0:,.2f}")
print(f"   E-Transfer Count Matched: {matched_by_amount[2] if matched_by_amount[2] else 0}")
print(f"   E-Transfer Total Matched: ${matched_by_amount[3] if matched_by_amount[3] else 0:,.2f}")

# The real question: unmatched e-transfers that have NO corresponding payment
print(f"\n" + "=" * 140)
print("KEY FINDINGS:")
print("=" * 140)

unmatched_with_no_payment = unmatched_banking[0] - (matched_by_amount[2] or 0)
print(f"\n⚠️  E-TRANSFERS NOT YET RECORDED AS PAYMENTS:")
print(f"   Unmatched in banking: {unmatched_banking[0]}")
print(f"   Already matched to payments by amount: {matched_by_amount[2]}")
print(f"   STILL OUTSTANDING: {unmatched_with_no_payment}")
print(f"   Amount outstanding: ${(unmatched_banking[1] or 0) - (matched_by_amount[3] or 0):,.2f}")

# Show sample unmatched e-transfers with NO payment
print(f"\n" + "=" * 140)
print("SAMPLE UNMATCHED E-TRANSFERS (showing first 20):")
print("=" * 140)
print(f"{'Date':<12} | {'Amount':>10} | {'Description':<60} | Already Paid?")
print("-" * 140)

cur.execute('''
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description,
        (SELECT COUNT(*) FROM payments p 
         WHERE ABS(p.amount - bt.credit_amount) < 0.01 
         AND (p.payment_date::date = bt.transaction_date::date 
              OR p.payment_date::date = bt.transaction_date::date - interval '1 day'
              OR p.payment_date::date = bt.transaction_date::date + interval '1 day')) as payment_count
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND (bt.description ILIKE '%E-TRANSFER%' OR bt.description ILIKE '%ETRANSFER%')
      AND bt.reconciled_payment_id IS NULL
    ORDER BY bt.transaction_date DESC
    LIMIT 20;
''')

unmatched_samples = cur.fetchall()
for row in unmatched_samples:
    trans_id, trans_date, amount, description, pmt_count = row
    date_str = trans_date.strftime('%Y-%m-%d') if trans_date else 'N/A'
    desc_trunc = description[:59] if description else 'N/A'
    pmt_status = f"Yes ({pmt_count})" if pmt_count and pmt_count > 0 else "No"
    print(f"{date_str} | ${amount:>9.2f} | {desc_trunc:<60} | {pmt_status}")

print(f"\n" + "=" * 140)
print("CONCLUSION:")
print("=" * 140)
print(f"""
If {unmatched_with_no_payment} e-transfers have NO corresponding payments:
  ❌ We have a GAP in reconciliation
  → Need to create payment records for these

If most unmatched e-transfers already show payment records:
  ✅ We already did our job correctly
  → Just need to update banking_transactions.reconciled_payment_id to mark them as linked
""")

print("=" * 140 + "\n")

cur.close()
conn.close()
