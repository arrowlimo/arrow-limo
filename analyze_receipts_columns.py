#!/usr/bin/env python3
"""Analyze receipts table for empty/sparse columns."""
import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', database='almsdata', password='***REMOVED***')
cur = conn.cursor()

# Get all columns
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")
columns = [row[0] for row in cur.fetchall()]

print("RECEIPTS TABLE - DATA DENSITY ANALYSIS")
print("=" * 80)

# Analyze each column
for col in columns:
    cur.execute(f"""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(CASE WHEN {col} IS NOT NULL AND CAST({col} AS TEXT) != '' THEN 1 END) as non_null,
            COUNT(CASE WHEN {col} IS NULL THEN 1 END) as null_count
        FROM receipts
    """)
    total, non_null, null_count = cur.fetchone()
    
    if total > 0:
        pct = (non_null / total) * 100
        status = "✓ USED" if pct > 20 else "⚠ SPARSE" if pct > 0 else "✗ EMPTY"
        print(f"{col:30} {status:12} {pct:6.1f}% ({non_null:6}/{total})")

print("\n" + "=" * 80)
print("\nSUMMARY:")
print("✓ USED   = >20% non-null (keep)")
print("⚠ SPARSE = 1-20% non-null (consider keeping)")
print("✗ EMPTY  = 0% non-null (can drop)")

cur.close()
conn.close()
