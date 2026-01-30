#!/usr/bin/env python3
"""Find and analyze general journal entries in receipts table."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*70)
print("GENERAL JOURNAL ENTRIES IN RECEIPTS")
print("="*70)

# Check for journal entries by source_system
print("\n1. Receipts by source_system:")
cur.execute("""
    SELECT 
        COALESCE(source_system, 'NULL') as source,
        COUNT(*) as count
    FROM receipts
    GROUP BY source_system
    ORDER BY count DESC
""")

for row in cur.fetchall():
    source, count = row
    if 'journal' in source.lower() or 'gl' in source.lower():
        print(f"   ⚠️  {source}: {count:,}")
    else:
        print(f"   {source}: {count:,}")

# Check for journal-related descriptions
print("\n2. Searching for 'journal' in descriptions:")
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE description ILIKE '%journal%' 
       OR vendor_name ILIKE '%journal%'
       OR source_system ILIKE '%journal%'
""")
journal_count = cur.fetchone()[0]
print(f"   Found {journal_count:,} receipts with 'journal' in fields")

if journal_count > 0:
    print("\n3. Sample journal entries:")
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            source_system,
            verified_source
        FROM receipts
        WHERE description ILIKE '%journal%' 
           OR vendor_name ILIKE '%journal%'
           OR source_system ILIKE '%journal%'
        ORDER BY receipt_date DESC
        LIMIT 20
    """)
    
    print(f"\n   {'Date':<12} {'Vendor':<20} {'Amount':>12} {'Source System':<20}")
    print("   " + "-" * 80)
    for row in cur.fetchall():
        date, vendor, desc, amount, source_sys, verified = row
        vendor_str = (vendor or 'NULL')[:18]
        source_str = (source_sys or 'NULL')[:18]
        print(f"   {date} {vendor_str:<20} ${amount:>10,.2f} {source_str:<20}")

# Check for GL-related entries
print("\n4. Searching for GL/General Ledger entries:")
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE description ILIKE '%general ledger%' 
       OR description ILIKE '%g/l%'
       OR description ILIKE '% gl %'
       OR source_system ILIKE '%gl%'
""")
gl_count = cur.fetchone()[0]
print(f"   Found {gl_count:,} receipts with GL references")

# Check for adjustment-type entries
print("\n5. Searching for adjustments/corrections:")
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE description ILIKE '%adjustment%' 
       OR description ILIKE '%correction%'
       OR description ILIKE '%reclassif%'
""")
adj_count = cur.fetchone()[0]
print(f"   Found {adj_count:,} receipts that are adjustments/corrections")

if adj_count > 0:
    print("\n6. Sample adjustment entries:")
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            description,
            gross_amount,
            source_system
        FROM receipts
        WHERE description ILIKE '%adjustment%' 
           OR description ILIKE '%correction%'
           OR description ILIKE '%reclassif%'
        ORDER BY receipt_date DESC
        LIMIT 10
    """)
    
    print(f"\n   {'Date':<12} {'Vendor':<25} {'Amount':>12} {'Description'}")
    print("   " + "-" * 90)
    for row in cur.fetchall():
        date, vendor, desc, amount, source_sys = row
        vendor_str = (vendor or 'NULL')[:23]
        desc_str = (desc or 'NULL')[:40]
        print(f"   {date} {vendor_str:<25} ${amount:>10,.2f} {desc_str}")

print(f"\n{'='*70}")
print("RECOMMENDATION")
print("="*70)
print("""
Journal entries should NOT be in the receipts table because:
  - Receipts = actual expenses/transactions with supporting documents
  - Journal entries = accounting adjustments without physical receipts
  
Journal entries belong in a separate 'journal_entries' table.

If these are present, they should be:
  1. Exported for review
  2. Moved to a proper journal_entries table
  3. Removed from receipts table
""")

cur.close()
conn.close()
