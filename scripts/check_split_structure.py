#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check how existing splits are stored
cur.execute("""
    SELECT receipt_id, vendor_name, gross_amount, parent_receipt_id, 
           split_key, split_group_total, is_split_receipt, description
    FROM receipts 
    WHERE is_split_receipt = TRUE 
    LIMIT 5
""")

print("Sample Split Receipts:")
print("-" * 120)
for row in cur.fetchall():
    print(f"ID: {row[0]:<8} | Vendor: {row[1]:<20} | Amount: ${row[2]:>8} | Parent: {row[3]} | Split Key: {row[4]}")
    print(f"  Description: {row[7]}")
    print()

conn.close()
