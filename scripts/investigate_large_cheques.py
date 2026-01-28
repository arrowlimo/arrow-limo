#!/usr/bin/env python3
"""Investigate the two large CHEQUE receipts (955.46 and WO -120.00)."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("INVESTIGATION: TWO LARGE CHEQUES")
print("=" * 100 + "\n")

# Look up the large CHEQUES
print("1. CHEQUE 955.46 ($195,406.00, Oct 31, 2012)")
print("-" * 100)

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date, description, 
           gl_account_code, banking_transaction_id, created_from_banking
    FROM receipts
    WHERE receipt_id = 142987
""")

result = cur.fetchone()
if result:
    receipt_id, vendor, amount, date, desc, gl, banking_id, from_banking = result
    print(f"Receipt ID: {receipt_id}")
    print(f"Vendor: {vendor}")
    print(f"Amount: ${amount:,.2f}")
    print(f"Date: {date}")
    print(f"Description: {desc}")
    print(f"GL Code: {gl}")
    print(f"Banking Transaction ID: {banking_id}")
    print(f"Created from Banking: {from_banking}")
    print()

# Check if there's a corresponding banking transaction around that date
print("\nBanking transactions from Oct 2012:")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, verified
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND EXTRACT(MONTH FROM transaction_date) = 10
    ORDER BY transaction_date, debit_amount DESC, credit_amount DESC
    LIMIT 10
""")

for trans_id, trans_date, trans_desc, debit, credit, verified in cur.fetchall():
    amount = (debit or 0) if (debit or 0) > 0 else (credit or 0)
    if amount > 50000 or "955" in trans_desc or "cheque" in trans_desc.lower():
        print(f"  Transaction {trans_id} | {trans_date} | ${amount:,.2f}")
        print(f"    Desc: {trans_desc}")

print("\n" + "=" * 100)
print("2. CHEQUE WO -120.00 ($158,362.70, Jul 13, 2012)")
print("-" * 100)

cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, receipt_date, description, 
           gl_account_code, banking_transaction_id, created_from_banking
    FROM receipts
    WHERE receipt_id = 142648
""")

result = cur.fetchone()
if result:
    receipt_id, vendor, amount, date, desc, gl, banking_id, from_banking = result
    print(f"Receipt ID: {receipt_id}")
    print(f"Vendor: {vendor}")
    print(f"Amount: ${amount:,.2f}")
    print(f"Date: {date}")
    print(f"Description: {desc}")
    print(f"GL Code: {gl}")
    print(f"Banking Transaction ID: {banking_id}")
    print(f"Created from Banking: {from_banking}")
    print()

# Check if there's a corresponding banking transaction around that date
print("\nBanking transactions from Jul 2012:")
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, verified
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND EXTRACT(MONTH FROM transaction_date) = 7
    ORDER BY transaction_date, debit_amount DESC, credit_amount DESC
    LIMIT 10
""")

for trans_id, trans_date, trans_desc, debit, credit, verified in cur.fetchall():
    amount = (debit or 0) if (debit or 0) > 0 else (credit or 0)
    if amount > 50000 or "120" in trans_desc or "cheque" in trans_desc.lower():
        print(f"  Transaction {trans_id} | {trans_date} | ${amount:,.2f}")
        print(f"    Desc: {trans_desc}")

print("\n" + "=" * 100)
print("INTERPRETATION GUIDANCE")
print("=" * 100)
print("""
These appear to be historical CHEQUE entries with no banking links. 
Possible interpretations:

1. "CHEQUE 955.46" - Vendor name is "955.46" (possibly a cheque number or reference)
   - This is a very large amount ($195,406)
   - GL Code should clarify purpose (expense, transfer, etc.)
   
2. "CHEQUE WO -120.00" - "WO" likely means "Write Off" or "Withdrawal"
   - The "-120.00" might be a memo field
   - This is also a large amount ($158,362.70)

QUESTIONS FOR USER:
- Should these large CHEQUES be verified/investigated further?
- Are they legitimate historical transactions?
- What GL codes are assigned (are they correct)?
- Should they remain in the system or be marked for review?
""")

cur.close()
conn.close()

print("✅ Analysis complete")
