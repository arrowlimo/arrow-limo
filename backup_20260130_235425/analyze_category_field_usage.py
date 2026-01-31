#!/usr/bin/env python3
"""Analyze current usage of category fields before removal."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()

print("=" * 100)
print("CATEGORY FIELD USAGE ANALYSIS")
print("=" * 100)

# Check category field usage
print("\n1. RECEIPTS.CATEGORY field usage:")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(category) as with_category,
        COUNT(gl_account_code) as with_gl_code,
        COUNT(CASE WHEN category IS NOT NULL AND gl_account_code IS NULL THEN 1 END) as cat_no_gl,
        COUNT(CASE WHEN category IS NULL AND gl_account_code IS NOT NULL THEN 1 END) as gl_no_cat,
        COUNT(CASE WHEN category IS NOT NULL AND gl_account_code IS NOT NULL THEN 1 END) as both
    FROM receipts
""")
row = cur.fetchone()
print(f"  Total receipts: {row[0]:,}")
print(f"  With category: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")
print(f"  With gl_account_code: {row[2]:,} ({row[2]/row[0]*100:.1f}%)")
print(f"  Category but NO GL code: {row[3]:,}")
print(f"  GL code but NO category: {row[4]:,}")
print(f"  Both category AND GL code: {row[5]:,}")

# Check tax_category field
print("\n2. RECEIPTS.TAX_CATEGORY field usage:")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(tax_category) as with_tax_category
    FROM receipts
""")
row = cur.fetchone()
print(f"  Total receipts: {row[0]:,}")
print(f"  With tax_category: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")

# Check gl_subcategory field
print("\n3. RECEIPTS.GL_SUBCATEGORY field usage:")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(gl_subcategory) as with_gl_subcategory
    FROM receipts
""")
row = cur.fetchone()
print(f"  Total receipts: {row[0]:,}")
print(f"  With gl_subcategory: {row[1]:,} ({row[1]/row[0]*100:.1f}%)")

# Check if category values map to GL codes
print("\n4. Category to GL code mapping:")
cur.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        COUNT(DISTINCT gl_account_code) as gl_codes,
        STRING_AGG(DISTINCT gl_account_code, ', ') as gl_list
    FROM receipts
    WHERE category IS NOT NULL
    GROUP BY category
    ORDER BY count DESC
    LIMIT 20
""")
print(f"{'Category':<40} {'Count':>10} {'GL Codes':>10} {'GL List'}")
print("-" * 100)
for row in cur.fetchall():
    print(f"{row[0]:<40} {row[1]:>10,} {row[2]:>10} {row[3] or 'NULL'}")

# Check scripts/code that reference these fields
print("\n5. RECOMMENDATION:")
if row[3] > 0:  # cat_no_gl from first query
    print("  ⚠ WARNING: Some receipts have category but no GL code")
    print("  → First run migration to copy category data to GL codes")
else:
    print("  ✓ Safe to drop category fields")
    print("  → All receipts with categories also have GL codes")

cur.close()
conn.close()
