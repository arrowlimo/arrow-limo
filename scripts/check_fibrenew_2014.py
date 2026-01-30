#!/usr/bin/env python
"""
Check Fibrenew data for 2014
Looking for invoice 5386 or any Fibrenew invoices from 2014
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("FIBRENEW 2014 SEARCH")
print("=" * 80)

# Search ALL 2014 receipts for Fibrenew
print("\n1. ALL Fibrenew receipts in 2014:")
cur.execute("""
    SELECT 
        receipt_id, receipt_date, vendor_name, gross_amount, 
        description, source_reference
    FROM receipts
    WHERE vendor_name ILIKE '%fibr%'
        AND EXTRACT(YEAR FROM receipt_date) = 2014
    ORDER BY receipt_date
""")
receipts_2014 = cur.fetchall()

if receipts_2014:
    print(f"\n✅ Found {len(receipts_2014)} Fibrenew receipts in 2014:")
    for r in receipts_2014:
        desc = r[4][:60] if r[4] else "N/A"
        ref = r[5] if r[5] else "N/A"
        print(f"  {r[1]} | ${r[3]:>10,.2f} | {r[2]:30s} | Ref: {ref} | {desc}")
else:
    print("\n❌ No Fibrenew receipts found in 2014")

# Search ALL 2014 banking for Fibrenew
print("\n\n2. ALL Fibrenew banking transactions in 2014:")
cur.execute("""
    SELECT 
        transaction_id, transaction_date, description, 
        debit_amount, credit_amount, category, account_number
    FROM banking_transactions
    WHERE description ILIKE '%fibr%'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
    ORDER BY transaction_date
""")
banking_2014 = cur.fetchall()

if banking_2014:
    print(f"\n✅ Found {len(banking_2014)} Fibrenew banking transactions in 2014:")
    for b in banking_2014:
        amount = b[3] if b[3] else -b[4]
        print(f"  {b[1]} | ${amount:>10,.2f} | Acct: {b[6]} | {b[2][:65]}")
else:
    print("\n❌ No Fibrenew banking transactions found in 2014")

# Check if invoice 5386 mentioned in 2014
print("\n\n3. Invoice 5386 in 2014:")
cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
    FROM receipts
    WHERE (description ILIKE '%5386%' OR source_reference = '5386')
        AND EXTRACT(YEAR FROM receipt_date) = 2014
""")
inv_5386_2014 = cur.fetchall()

if inv_5386_2014:
    print(f"\n✅ Found {len(inv_5386_2014)} reference(s) to 5386 in 2014:")
    for r in inv_5386_2014:
        print(f"  {r[1]} | ${r[3]:>10,.2f} | {r[2]} | {r[4][:60]}")
else:
    print("\n❌ No invoice 5386 found in 2014")

# Check total 2014 data
print("\n\n4. Overall 2014 data:")
cur.execute("""
    SELECT COUNT(*), MIN(receipt_date), MAX(receipt_date)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2014
""")
count_2014 = cur.fetchone()
print(f"  2014 receipts: {count_2014[0]} records from {count_2014[1]} to {count_2014[2]}")

cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2014
""")
banking_count = cur.fetchone()
print(f"  2014 banking: {banking_count[0]} records from {banking_count[1]} to {banking_count[2]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
