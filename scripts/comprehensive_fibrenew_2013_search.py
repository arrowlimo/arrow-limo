#!/usr/bin/env python
"""
Comprehensive Fibrenew 2013 Search
Looking for invoice 5386 dated 03/03/2013
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
print("COMPREHENSIVE FIBRENEW 2013 SEARCH")
print("=" * 80)

# Search ALL 2013 receipts for Fibrenew (case-insensitive, any variation)
print("\n1. ALL Fibrenew receipts in 2013:")
cur.execute("""
    SELECT 
        receipt_id, receipt_date, vendor_name, gross_amount, 
        description, source_reference
    FROM receipts
    WHERE vendor_name ILIKE '%fibr%'
        AND EXTRACT(YEAR FROM receipt_date) = 2013
    ORDER BY receipt_date
""")
receipts_2013 = cur.fetchall()

if receipts_2013:
    print(f"\n✅ Found {len(receipts_2013)} Fibrenew receipts in 2013:")
    for r in receipts_2013:
        print(f"  {r[1]} | ${r[3]:>10,.2f} | {r[2]:30s} | Ref: {r[5]} | {r[4][:60]}")
else:
    print("\n❌ No Fibrenew receipts found in 2013")

# Search ALL 2013 banking for Fibrenew
print("\n\n2. ALL Fibrenew banking transactions in 2013:")
cur.execute("""
    SELECT 
        transaction_id, transaction_date, description, 
        debit_amount, credit_amount, category
    FROM banking_transactions
    WHERE description ILIKE '%fibr%'
        AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date
""")
banking_2013 = cur.fetchall()

if banking_2013:
    print(f"\n✅ Found {len(banking_2013)} Fibrenew banking transactions in 2013:")
    for b in banking_2013:
        amount = b[3] if b[3] else -b[4]
        print(f"  {b[1]} | ${amount:>10,.2f} | {b[2][:70]}")
else:
    print("\n❌ No Fibrenew banking transactions found in 2013")

# Search for invoice 5386 anywhere
print("\n\n3. Invoice 5386 mentioned ANYWHERE in database:")
cur.execute("""
    SELECT 'receipts' as source, receipt_id as id, receipt_date as date, 
           vendor_name, gross_amount, description
    FROM receipts
    WHERE description ILIKE '%5386%' OR source_reference = '5386'
    UNION ALL
    SELECT 'banking' as source, transaction_id as id, transaction_date as date,
           vendor_extracted, debit_amount, description
    FROM banking_transactions
    WHERE description ILIKE '%5386%'
    ORDER BY date
""")
inv_5386 = cur.fetchall()

if inv_5386:
    print(f"\n✅ Found {len(inv_5386)} reference(s) to invoice 5386:")
    for i in inv_5386:
        amount = i[4] if i[4] is not None else 0.0
        vendor = i[3] if i[3] else "N/A"
        print(f"  Source: {i[0]:10s} | ID: {i[1]:6d} | Date: {i[2]} | Amount: ${amount:>10,.2f}")
        print(f"  Vendor: {vendor} | Desc: {i[5][:70]}")
        print()
else:
    print("\n❌ Invoice 5386 not found anywhere in system")

# Check if we have ANY 2013 data at all
print("\n\n4. Do we have ANY receipt data from 2013?")
cur.execute("""
    SELECT COUNT(*), MIN(receipt_date), MAX(receipt_date)
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2013
""")
count_2013 = cur.fetchone()
print(f"  2013 receipts: {count_2013[0]} records from {count_2013[1]} to {count_2013[2]}")

cur.execute("""
    SELECT COUNT(*), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2013
""")
banking_count = cur.fetchone()
print(f"  2013 banking: {banking_count[0]} records from {banking_count[1]} to {banking_count[2]}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
print("\nRECOMMENDATION:")
print("  If invoice 5386 from 03/03/2013 should exist, it was likely:")
print("  1. Never imported into the digital system")
print("  2. Part of a data migration gap (2013 data missing)")
print("  3. Recorded under a different vendor name")
print("  4. In a separate offline/paper-based system")
