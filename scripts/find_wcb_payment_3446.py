#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Find the WCB payment of $3,446.02 from August 30, 2012"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("SEARCHING FOR WCB PAYMENT $3,446.02 (August 2012)")
print("=" * 80)

# First, let's check what columns exist
print("\n1. Checking banking_transactions table columns...")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print(f"Columns: {', '.join(cols)}")

# Search for exact amount (using correct column name)
print("\n2. Searching for exact amount 3446.02...")
cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, description, vendor_extracted
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-08-15' AND '2012-09-15'
    AND (ABS(COALESCE(debit_amount, 0) - 3446.02) < 1 OR ABS(COALESCE(credit_amount, 0) - 3446.02) < 1)
    ORDER BY transaction_date
""")
rows = cur.fetchall()
print(f"Found {len(rows)} transactions:")
for r in rows:
    debit_amt = r[2] if r[2] else 0
    credit_amt = r[3] if r[3] else 0
    print(f"  ID: {r[0]:6d} | Date: {r[1]} | Debit: ${debit_amt:>10.2f} | Credit: ${credit_amt:>10.2f} | Vendor: {r[5]} | Desc: {str(r[4])[:50] if r[4] else ''}")

# Search for WCB vendor around that date
print("\n3. Searching for all WCB transactions (Aug-Sep 2012)...")
cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, credit_amount, description, vendor_extracted
    FROM banking_transactions
    WHERE transaction_date BETWEEN '2012-08-01' AND '2012-09-30'
    AND (vendor_extracted ILIKE '%wcb%' OR description ILIKE '%wcb%')
    ORDER BY transaction_date, debit_amount DESC NULLS LAST, credit_amount DESC NULLS LAST
""")
rows = cur.fetchall()
print(f"Found {len(rows)} WCB transactions:")
for r in rows:
    debit_amt = r[2] if r[2] else 0
    credit_amt = r[3] if r[3] else 0
    print(f"  ID: {r[0]:6d} | Date: {r[1]} | Debit: ${debit_amt:>10.2f} | Credit: ${credit_amt:>10.2f} | Vendor: {r[5]} | Desc: {str(r[4])[:50] if r[4] else ''}")

# Check receipts table for this amount
print("\n4. Checking receipts table for $3,446.02...")
cur.execute("""
    SELECT receipt_id, receipt_date, gross_amount, vendor, description, banking_transaction_id
    FROM receipts
    WHERE receipt_date BETWEEN '2012-08-15' AND '2012-09-15'
    AND ABS(gross_amount - 3446.02) < 1
    ORDER BY receipt_date
""")
rows = cur.fetchall()
print(f"Found {len(rows)} receipts:")
for r in rows:
    print(f"  ID: {r[0]:6d} | Date: {r[1]} | Amount: ${r[2]:>10.2f} | Vendor: {r[3]} | Banking ID: {r[5]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("Search complete!")
print("=" * 80)
