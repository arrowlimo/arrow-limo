#!/usr/bin/env python3
"""
Show FULL banking descriptions for POINT OF SALE receipts
to see if there's additional vendor information we're missing
"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Get all POINT OF SALE receipts with FULL banking descriptions
cur.execute("""
    SELECT 
        r.vendor_name,
        bt.description as banking_desc,
        bt.debit_amount,
        bt.transaction_date,
        r.description as receipt_desc
    FROM receipts r
    INNER JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE (r.vendor_name ILIKE '%point%of%sale%' OR r.vendor_name ILIKE '%pointofsale%')
      AND r.vendor_name NOT ILIKE '%peavey%'
      AND r.vendor_name NOT ILIKE '%pack%post%'
    ORDER BY bt.transaction_date DESC
    LIMIT 100
""")

print("FULL BANKING DESCRIPTIONS FOR POINT OF SALE RECEIPTS")
print("=" * 120)
print()

for row in cur.fetchall():
    vendor, banking_desc, amount, date, receipt_desc = row
    print(f"Date: {date} | Amount: ${amount:>8.2f}")
    print(f"Current Vendor: {vendor[:80]}")
    print(f"Banking:        {banking_desc}")
    if receipt_desc and 'AUTO-GEN' not in receipt_desc:
        print(f"Receipt Desc:   {receipt_desc[:80]}")
    print("-" * 120)

cur.close()
conn.close()
