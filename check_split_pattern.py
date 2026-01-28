#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

# Find receipts that are part of a split (have split_group_id)
cur.execute("""
    SELECT 
        split_group_id,
        COUNT(*) as count,
        SUM(gross_amount) as total,
        STRING_AGG(receipt_id::text, ', ' ORDER BY receipt_id) as receipt_ids
    FROM receipts 
    WHERE split_group_id IS NOT NULL
    GROUP BY split_group_id
    LIMIT 5
""")

print("=== EXISTING SPLIT GROUPS ===")
for row in cur.fetchall():
    print(f"Group {row[0]}: {row[1]} receipts, Total: ${row[2]:,.2f}, IDs: {row[3]}")

# Check if there are any receipts marked as is_split_receipt = true
cur.execute("""
    SELECT COUNT(*) FROM receipts WHERE is_split_receipt = true
""")
print(f"\nReceipts marked as is_split_receipt: {cur.fetchone()[0]}")

# Check the split_group_total field
cur.execute("""
    SELECT receipt_id, gross_amount, split_group_total, is_split_receipt, parent_receipt_id
    FROM receipts 
    WHERE split_group_total IS NOT NULL 
    LIMIT 3
""")
print("\n=== RECEIPTS WITH split_group_total ===")
for row in cur.fetchall():
    print(f"Receipt #{row[0]}: gross=${row[1]}, group_total=${row[2]}, is_split={row[3]}, parent_id={row[4]}")

# Check a specific example
cur.execute("""
    SELECT receipt_id, split_group_id, gross_amount, is_split_receipt, parent_receipt_id
    FROM receipts 
    WHERE split_group_id IS NOT NULL
    LIMIT 10
""")
print("\n=== SAMPLE SPLIT RECEIPTS ===")
for row in cur.fetchall():
    print(f"Receipt #{row[0]}: group_id={row[1]}, amount=${row[2]}, is_split={row[3]}, parent={row[4]}")

cur.close()
conn.close()
