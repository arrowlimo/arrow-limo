#!/usr/bin/env python3
"""
Investigate POINT OF SALE receipts to extract vendor information
The vendor name is often truncated - need to look at linked banking transactions
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get all POINT OF SALE receipts with their banking descriptions
cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        bt.description as banking_desc,
        r.description as receipt_desc
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE r.vendor_name ILIKE '%point%of%sale%'
       OR r.vendor_name ILIKE '%pointofsale%'
    ORDER BY r.vendor_name
    LIMIT 200
""")

print("POINT OF SALE RECEIPTS - BANKING INVESTIGATION")
print("=" * 120)

for row in cur.fetchall():
    receipt_id, vendor, banking_desc, receipt_desc = row
    print(f"\nVendor: {vendor}")
    if banking_desc:
        print(f"Banking: {banking_desc[:100]}")
    if receipt_desc:
        print(f"Receipt: {receipt_desc[:100]}")

cur.close()
conn.close()
