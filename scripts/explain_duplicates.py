#!/usr/bin/env python3
"""Analyze the 28,483 duplicates - what years and sources are they from?"""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("="*70)
print("ANALYZING THE 28,483 DUPLICATES")
print("="*70)

# Check if ANY verified receipts are marked as duplicates
cur.execute("""
    SELECT COUNT(*) 
    FROM receipts 
    WHERE is_verified_banking IS TRUE 
    AND potential_duplicate IS TRUE
""")
verified_dupes = cur.fetchone()[0]
print(f"\nVerified banking receipts marked as duplicate: {verified_dupes}")
print("(Should be ZERO - verified are clean)\n")

# Year breakdown of duplicates
print("="*70)
print("DUPLICATES BY YEAR")
print("="*70)

cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM receipt_date) as year,
        COUNT(*) as count
    FROM receipts
    WHERE potential_duplicate IS TRUE
    GROUP BY year
    ORDER BY year
""")

print(f"\n{'Year':<10} {'Duplicate Count':>15}")
print("-" * 30)
for row in cur.fetchall():
    year = int(row[0]) if row[0] else 0
    count = row[1]
    print(f"{year:<10} {count:>15,}")

# Source system breakdown
print(f"\n{'='*70}")
print("DUPLICATES BY SOURCE SYSTEM")
print("="*70)

cur.execute("""
    SELECT 
        COALESCE(source_system, 'NULL') as source,
        COUNT(*) as count
    FROM receipts
    WHERE potential_duplicate IS TRUE
    GROUP BY source_system
    ORDER BY count DESC
""")

print(f"\n{'Source System':<30} {'Count':>15}")
print("-" * 50)
for row in cur.fetchall():
    source = row[0]
    count = row[1]
    print(f"{source:<30} {count:>15,}")

# Sample duplicates
print(f"\n{'='*70}")
print("SAMPLE DUPLICATE GROUPS (Top 5)")
print("="*70)

cur.execute("""
    SELECT 
        receipt_date,
        gross_amount,
        vendor_name,
        description,
        COUNT(*) as dup_count
    FROM receipts
    WHERE potential_duplicate IS TRUE
    GROUP BY receipt_date, gross_amount, vendor_name, description
    ORDER BY dup_count DESC
    LIMIT 5
""")

print(f"\n{'Date':<12} {'Amount':>12} {'Count':>6} {'Vendor':<20} {'Description'}")
print("-" * 90)
for row in cur.fetchall():
    date, amount, vendor, desc, count = row
    vendor_str = (vendor or 'NULL')[:18]
    desc_str = (desc or 'NULL')[:30]
    print(f"{date} ${amount:>10,.2f} {count:>6} {vendor_str:<20} {desc_str}")

print(f"\n{'='*70}")
print("EXPLANATION")
print("="*70)
print("""
The 28,483 duplicates are from YEARS 2018-2025 (the receipts we KEPT).

When we:
  1. Deleted receipts for 2012-2017 (the verified years)
  2. Rebuilt ONLY those years from verified banking (4,071 clean receipts)
  3. KEPT all receipts from 2018-2025 (46,503 receipts)

The duplicate detection ran on ALL receipts including 2018-2025.

These duplicates are likely:
  - Multiple imports from different sources
  - QuickBooks duplications from account 8362 (if it exists in later years)
  - Legitimate recurring payments (same amount, different dates = OK)
  - NSF fees appearing multiple times
""")

cur.close()
conn.close()
