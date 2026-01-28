import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

# Add split_group_id column if it doesn't exist
try:
    cur.execute("""
        ALTER TABLE receipts
        ADD COLUMN split_group_id INTEGER DEFAULT NULL
    """)
    conn.commit()
    print("✅ Added split_group_id column to receipts table")
except psycopg2.errors.DuplicateColumn:
    print("✅ split_group_id column already exists")
    conn.rollback()

# Now link the two FAS GAS receipts (157740 and 140760) with the same split_group_id
# We'll use receipt 157740's ID as the group ID (both should point to same group)
cur.execute("""
    UPDATE receipts
    SET split_group_id = 157740
    WHERE receipt_id IN (157740, 140760)
""")

conn.commit()
print(f"✅ Linked receipts 157740 + 140760 with split_group_id = 157740")

# Verify
cur.execute("""
    SELECT receipt_id, gross_amount, split_group_id, description
    FROM receipts
    WHERE receipt_id IN (157740, 140760)
    ORDER BY receipt_id
""")

print("\n📋 Verification:")
for rec_id, amt, group_id, desc in cur.fetchall():
    print(f"  Receipt #{rec_id}: ${amt} | split_group_id={group_id}")
    print(f"    {desc[:60]}")

cur.close()
conn.close()
