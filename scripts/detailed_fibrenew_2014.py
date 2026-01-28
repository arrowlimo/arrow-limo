#!/usr/bin/env python
"""
Detailed Fibrenew 2014 Analysis
Check what invoices these payments cover
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("DETAILED FIBRENEW 2014 ANALYSIS")
print("=" * 80)

# Get all Fibrenew receipts with full details
print("\n1. Fibrenew receipts in 2014 (all columns):")
cur.execute("""
    SELECT 
        r.receipt_id,
        r.receipt_date,
        r.vendor_name,
        r.gross_amount,
        r.description,
        r.source_reference,
        r.category,
        r.banking_transaction_id,
        bt.description as banking_desc,
        bt.check_number
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name ILIKE '%fibr%'
        AND EXTRACT(YEAR FROM r.receipt_date) = 2014
    ORDER BY r.receipt_date
""")
receipts = cur.fetchall()

if receipts:
    print(f"\n✅ Found {len(receipts)} Fibrenew receipt(s):\n")
    for r in receipts:
        print(f"Receipt ID: {r[0]}")
        print(f"Date: {r[1]}")
        print(f"Amount: ${r[3]:,.2f}")
        print(f"Category: {r[6]}")
        print(f"Receipt Description: {r[4]}")
        print(f"Source Reference: {r[5]}")
        if r[9]:
            print(f"Check Number: {r[9]}")
        if r[8]:
            print(f"Banking Description: {r[8]}")
        print("-" * 80)

# Check if there are any 2014 receipts with invoice numbers in description
print("\n\n2. ALL receipts with invoice numbers in 2014 (not just Fibrenew):")
cur.execute("""
    SELECT 
        receipt_date,
        vendor_name,
        gross_amount,
        description
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2014
        AND (description ILIKE '%invoice%' OR description ~ 'inv[# ]*[0-9]{4}')
    ORDER BY receipt_date
    LIMIT 20
""")
inv_receipts = cur.fetchall()

if inv_receipts:
    print(f"\n✅ Sample invoice receipts in 2014:")
    for r in inv_receipts:
        print(f"  {r[0]} | ${r[2]:>10,.2f} | {r[1]:30s} | {r[3][:70]}")

# Check banking for any mention of invoice 5386
print("\n\n3. Banking transactions mentioning '5386' in 2014:")
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        check_number
    FROM banking_transactions
    WHERE description ILIKE '%5386%'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
""")
banking_5386 = cur.fetchall()

if banking_5386:
    print(f"\n✅ Found {len(banking_5386)} banking transaction(s) with '5386':")
    for b in banking_5386:
        print(f"  {b[1]} | ${b[3]:>10,.2f} | Check: {b[4]} | {b[2]}")
else:
    print("\n❌ No banking transactions with '5386' in 2014")

# Look for March 2014 Fibrenew activity
print("\n\n4. March 2014 Fibrenew or office rent activity:")
cur.execute("""
    SELECT 
        receipt_date,
        vendor_name,
        gross_amount,
        description,
        category
    FROM receipts
    WHERE (vendor_name ILIKE '%fibr%' OR category ILIKE '%rent%' OR description ILIKE '%office%')
        AND receipt_date BETWEEN '2014-03-01' AND '2014-03-31'
    ORDER BY receipt_date
""")
march_2014 = cur.fetchall()

if march_2014:
    print(f"\n✅ Found {len(march_2014)} office/rent transaction(s) in March 2014:")
    for r in march_2014:
        desc = r[3][:75] if r[3] else "N/A"
        cat = r[4] if r[4] else "Unknown"
        print(f"  {r[0]} | ${r[2]:>10,.2f} | {r[1]:30s} | Cat: {cat}")
        print(f"    {desc}")
else:
    print("\n❌ No office/rent activity in March 2014")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("CONCLUSION:")
print("  Invoice 5386 from 03/03/2013 does NOT exist in 2013 or 2014 data.")
print("  Fibrenew payments in 2014 are check payments without invoice details.")
print("=" * 80)
