#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Check receipts with CO-OP in vendor name (excluding insurance)
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'receipts' AND column_name LIKE '%amount%'
""")
print("Amount columns:", [row[0] for row in cur.fetchall()])

cur.execute("""
    SELECT 
        r.receipt_id,
        r.vendor_name,
        r.description,
        r.receipt_date,
        bt.description as banking_desc
    FROM receipts r
    LEFT JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE (r.vendor_name ILIKE '%co-op%' OR r.vendor_name ILIKE '%coop%')
      AND r.vendor_name NOT ILIKE '%insurance%'
    ORDER BY r.receipt_date DESC
    LIMIT 100
""")

print("RECENT CO-OP RECEIPTS (last 100, excluding insurance)")
print("=" * 120)
for row in cur.fetchall():
    receipt_id, vendor, desc, date, banking_desc = row
    print(f"\n{date} | {vendor}")
    if desc:
        print(f"  Receipt desc: {desc[:80]}")
    if banking_desc:
        print(f"  Banking desc: {banking_desc[:80]}")

cur.close()
conn.close()
