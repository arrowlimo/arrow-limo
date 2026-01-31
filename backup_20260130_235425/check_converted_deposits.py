#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("VERIFICATION OF CONVERTED DEPOSITS")
print("=" * 120)

# Check IFS NSF REFUND
print("\n1. IFS NSF REFUND (was: DEPOSIT FROM IFS)")
print("-" * 120)
cur.execute("""
    SELECT 
        r.receipt_id, r.vendor_name, r.gross_amount, r.description, r.receipt_date,
        bt.description, bt.debit_amount, bt.credit_amount
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'IFS NSF REFUND'
""")
for row in cur.fetchall():
    receipt_id, vendor, amount, desc, date, bank_desc, debit, credit = row
    amt = amount if amount else 0
    print(f"Receipt: {receipt_id} | {date} | Amount: ${amt:.2f}")
    print(f"  Description: {desc}")
    print(f"  Banking: {bank_desc}")
    print()

# Check INSURANCE/POLICY REFUND
print("\n2. INSURANCE/POLICY REFUND (was: DEPOSIT FROM CAMBRIDE ON)")
print("-" * 120)
cur.execute("""
    SELECT 
        r.receipt_id, r.vendor_name, r.gross_amount, r.description, r.receipt_date,
        bt.description, bt.debit_amount, bt.credit_amount
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name = 'INSURANCE/POLICY REFUND'
""")
for row in cur.fetchall():
    receipt_id, vendor, amount, desc, date, bank_desc, debit, credit = row
    amt = amount if amount else 0
    print(f"Receipt: {receipt_id} | {date} | Amount: ${amt:.2f}")
    print(f"  Description: {desc}")
    print(f"  Banking: {bank_desc}")
    print()

cur.close()
conn.close()
