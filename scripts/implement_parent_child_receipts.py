#!/usr/bin/env python
"""
Add parent_receipt_id column for easier split receipt management.
This replaces the complex split_key + is_split_receipt pattern.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("=" * 80)
print("IMPLEMENTING PARENT-CHILD RECEIPT LINKING")
print("=" * 80)

# Step 1: Add parent_receipt_id column
print("\n✅ Adding parent_receipt_id column...")
cur.execute("""
    ALTER TABLE receipts 
    ADD COLUMN IF NOT EXISTS parent_receipt_id BIGINT
""")
print("   Column added")

# Step 2: Add foreign key constraint (self-referencing)
print("\n✅ Adding foreign key constraint...")
cur.execute("""
    ALTER TABLE receipts 
    DROP CONSTRAINT IF EXISTS fk_receipts_parent
""")
cur.execute("""
    ALTER TABLE receipts 
    ADD CONSTRAINT fk_receipts_parent 
    FOREIGN KEY (parent_receipt_id) 
    REFERENCES receipts(receipt_id) 
    ON DELETE CASCADE
""")
print("   Foreign key constraint added")

# Step 3: Add index for fast parent lookups
print("\n✅ Creating index for parent lookups...")
cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_receipts_parent 
    ON receipts(parent_receipt_id) 
    WHERE parent_receipt_id IS NOT NULL
""")
print("   Index created")

# Step 4: Migrate existing split_key data to parent-child structure
print("\n✅ Migrating existing split_key data...")
cur.execute("""
    SELECT split_key, COUNT(*) as count 
    FROM receipts 
    WHERE split_key IS NOT NULL 
    GROUP BY split_key
""")
split_groups = cur.fetchall()

migrated_count = 0
for split_key, count in split_groups:
    # Get all receipts in this split group
    cur.execute("""
        SELECT receipt_id, gross_amount, receipt_date
        FROM receipts 
        WHERE split_key = %s
        ORDER BY receipt_id
    """, (split_key,))
    
    receipts = cur.fetchall()
    if len(receipts) < 2:
        continue
    
    # First receipt becomes the parent
    parent_id = receipts[0][0]
    
    # Remaining receipts become children
    for child_id, child_amount, child_date in receipts[1:]:
        cur.execute("""
            UPDATE receipts 
            SET parent_receipt_id = %s
            WHERE receipt_id = %s
        """, (parent_id, child_id))
        migrated_count += 1

print(f"   Migrated {migrated_count} child receipts from {len(split_groups)} split groups")

# Step 5: Add helper view for easy querying
print("\n✅ Creating helper view...")
cur.execute("""
    CREATE OR REPLACE VIEW receipt_splits AS
    SELECT 
        parent.receipt_id as parent_id,
        parent.receipt_date,
        parent.vendor_name,
        parent.gross_amount as parent_total,
        child.receipt_id as child_id,
        child.gross_amount as child_amount,
        child.category as child_category,
        child.is_personal_purchase as is_personal,
        child.description as child_description
    FROM receipts parent
    LEFT JOIN receipts child ON child.parent_receipt_id = parent.receipt_id
    WHERE parent.parent_receipt_id IS NULL
    AND (child.receipt_id IS NOT NULL OR 
         parent.receipt_id IN (SELECT DISTINCT parent_receipt_id FROM receipts WHERE parent_receipt_id IS NOT NULL))
    ORDER BY parent.receipt_id, child.receipt_id
""")
print("   View 'receipt_splits' created")

conn.commit()

# Show summary
print("\n" + "=" * 80)
print("SUMMARY - NEW SPLIT RECEIPT WORKFLOW")
print("=" * 80)
print("""
✅ parent_receipt_id column added
✅ Foreign key constraint added (self-referencing)
✅ Index created for fast lookups
✅ Existing split_key data migrated
✅ Helper view created

USAGE IN YOUR WORKBOOK:

Column to add: "Parent Receipt #" (optional - leave blank for normal receipts)

Example Entry:
  Row 1: Costco | $200.00 | [blank parent] ← This is the full receipt
         (System assigns receipt_id = 12345)
  
  Row 2: Costco | $60.00 | Parent: 12345 | Category: Fuel | Business
  Row 3: Costco | $80.00 | Parent: 12345 | Category: Office | Business  
  Row 4: Costco | $60.00 | Parent: 12345 | Category: Personal | Personal

QUERIES YOU CAN RUN:

-- Find all splits for a receipt
SELECT * FROM receipt_splits WHERE parent_id = 12345;

-- Find all parent receipts with splits
SELECT parent_id, vendor_name, parent_total, COUNT(child_id) as split_count
FROM receipt_splits
GROUP BY parent_id, vendor_name, parent_total
HAVING COUNT(child_id) > 0;

-- Validate split totals match parent
SELECT 
    parent_id,
    parent_total,
    SUM(child_amount) as split_total,
    parent_total - SUM(child_amount) as difference
FROM receipt_splits
GROUP BY parent_id, parent_total
HAVING ABS(parent_total - SUM(child_amount)) > 0.01;
""")

cur.close()
conn.close()
