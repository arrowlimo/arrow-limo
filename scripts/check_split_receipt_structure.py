#!/usr/bin/env python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Check current split handling
print("=" * 70)
print("CURRENT RECEIPTS TABLE STRUCTURE")
print("=" * 70)

cur.execute("""SELECT column_name, data_type FROM information_schema.columns 
WHERE table_name = 'receipts' ORDER BY ordinal_position""")
columns = cur.fetchall()
print(f"\nTotal columns: {len(columns)}")
for col_name, col_type in columns:
    print(f"  {col_name:<30} {col_type}")

# Look for any existing split references
print("\n" + "=" * 70)
print("EXISTING SPLIT/PERSONAL REFERENCES IN DATA")
print("=" * 70)

cur.execute("""SELECT COUNT(*) FROM receipts 
WHERE description ILIKE '%split%' OR description ILIKE '%personal%' OR description ILIKE '%portion%'""")
split_count = cur.fetchone()[0]
print(f"\nReceipts mentioning split/personal/portion: {split_count:,}")

# Show some examples
if split_count > 0:
    cur.execute("""SELECT receipt_id, receipt_date, vendor_name, gross_amount, description 
    FROM receipts 
    WHERE description ILIKE '%split%' OR description ILIKE '%personal%' OR description ILIKE '%portion%'
    LIMIT 5""")
    print("\nExamples:")
    for receipt_id, date, vendor, amount, desc in cur.fetchall():
        print(f"  [{receipt_id}] {date} | {vendor} | ${amount} | {desc[:50]}")

# Check for any existing parent/child or grouping structure
cur.execute("""SELECT * FROM information_schema.columns 
WHERE table_name = 'receipts' AND (column_name ILIKE '%parent%' OR column_name ILIKE '%group%' OR column_name ILIKE '%split%' OR column_name ILIKE '%related%')""")
split_cols = cur.fetchall()
print("\n" + "=" * 70)
print("EXISTING SPLIT/GROUPING COLUMNS")
print("=" * 70)
print(f"\nFound: {len(split_cols)}")
for col in split_cols:
    col_name = col[3]
    col_type = col[7]
    print(f"  {col_name:<30} {col_type}")

cur.close()
conn.close()
