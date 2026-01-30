#!/usr/bin/env python
"""
Analyze current split receipt usage and propose easiest entry method.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("SPLIT RECEIPT USAGE ANALYSIS")
print("=" * 80)

# Check how many splits are currently being used
cur.execute("""
    SELECT 
        COUNT(*) as total_split_receipts,
        COUNT(DISTINCT split_key) as unique_split_groups,
        AVG(CASE WHEN is_split_receipt THEN gross_amount ELSE NULL END) as avg_split_amount,
        SUM(CASE WHEN is_split_receipt THEN gross_amount ELSE 0 END) as total_split_value
    FROM receipts
    WHERE is_split_receipt = TRUE
""")
row = cur.fetchone()
if row[0]:
    print(f"\nCurrent split receipt usage:")
    print(f"  Total split receipt lines: {row[0]:,}")
    print(f"  Unique split groups: {row[1]:,}")
    print(f"  Average split line amount: ${row[2]:.2f}")
    print(f"  Total value in splits: ${row[3]:,.2f}")
else:
    print("\n⚠️  No receipts currently using is_split_receipt flag")

# Check split_key usage
cur.execute("""
    SELECT COUNT(DISTINCT split_key) 
    FROM receipts 
    WHERE split_key IS NOT NULL
""")
split_key_count = cur.fetchone()[0]
print(f"  Receipts with split_key: {split_key_count:,}")

# Look at actual split patterns
cur.execute("""
    SELECT 
        split_key,
        COUNT(*) as split_count,
        STRING_AGG(DISTINCT vendor_name, ', ') as vendors,
        SUM(gross_amount) as total_amount,
        MIN(receipt_date) as date
    FROM receipts
    WHERE split_key IS NOT NULL
    GROUP BY split_key
    ORDER BY split_count DESC
    LIMIT 10
""")

print("\n" + "=" * 80)
print("TOP 10 SPLIT GROUPS (if using split_key)")
print("=" * 80)
for split_key, count, vendors, total, date in cur.fetchall():
    print(f"\n{split_key}")
    print(f"  Parts: {count} | Total: ${total:,.2f} | Date: {date} | Vendor: {vendors[:50]}")

# Check for parent_id column (common pattern)
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    AND column_name IN ('parent_receipt_id', 'parent_id', 'master_receipt_id')
""")
parent_col = cur.fetchone()
if parent_col:
    print(f"\n✅ Found parent linking column: {parent_col[0]}")
else:
    print("\n❌ No parent linking column found")

# Look at personal purchase patterns
cur.execute("""
    SELECT 
        COUNT(*) as total_personal,
        SUM(gross_amount) as total_value,
        AVG(gross_amount) as avg_value
    FROM receipts
    WHERE is_personal_purchase = TRUE
""")
row = cur.fetchone()
if row[0]:
    print("\n" + "=" * 80)
    print("PERSONAL PURCHASE PATTERNS")
    print("=" * 80)
    print(f"  Personal purchase lines: {row[0]:,}")
    print(f"  Total personal value: ${row[1]:,.2f}")
    print(f"  Average personal amount: ${row[2]:.2f}")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("RECOMMENDED STRATEGY")
print("=" * 80)
print("""
EASIEST METHOD: Parent-Child Receipt Linking

Why this is better than split_key + is_split_receipt:
  ✅ One main receipt (the full receipt amount)
  ✅ Child receipts link back via parent_receipt_id
  ✅ No manual split_key generation
  ✅ No need to track split_group_total on every line
  ✅ Easy to query: "show me all splits for receipt #12345"
  
Entry workflow:
  1. Enter the FULL receipt first (e.g., Costco $200)
  2. Note the receipt_id (auto-generated)
  3. Enter child receipts with parent_receipt_id = that ID
     - Child 1: $60 fuel (business)
     - Child 2: $80 office (business)
     - Child 3: $60 personal
  
Database sees:
  Receipt 12345: Costco $200 (parent_receipt_id = NULL)
  Receipt 12346: Costco $60 fuel (parent_receipt_id = 12345)
  Receipt 12347: Costco $80 office (parent_receipt_id = 12345)
  Receipt 12348: Costco $60 personal (parent_receipt_id = 12345)
  
Validation:
  SELECT * FROM receipts WHERE parent_receipt_id = 12345
  Sum should equal parent receipt amount
""")
