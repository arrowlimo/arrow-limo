#!/usr/bin/env python3
"""
Fix categorization of General Journal entries in receipts.

General Journal entries are accounting adjustments and should be categorized
separately from vendor invoices. This script:

1. Adds 'general_journal' category to categorization logic
2. Recategorizes existing receipts from 'uncategorized' to 'general_journal'
3. Updates auto_create_receipts script for future imports

Created: November 25, 2025
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

print("\nFIXING GENERAL JOURNAL CATEGORIZATION")
print("="*80)

# Find receipts that should be general_journal
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        gross_amount,
        category
    FROM receipts
    WHERE (
        vendor_name ILIKE '%general journal%' 
        OR vendor_name ILIKE '%gen j%'
        OR vendor_name ILIKE 'gj %'
        OR description ILIKE '%general journal%'
        OR description ILIKE '%gen j%'
        OR description ILIKE 'gj %'
    )
    AND category != 'general_journal'
""")

to_fix = cur.fetchall()

print(f"\n1. Found {len(to_fix)} receipts to recategorize:")
print(f"   {'Date':>12} {'Amount':>12} {'Current':>20} {'Vendor':>40}")
for row in to_fix:
    rid, rdate, vendor, amt, cat = row
    print(f"   {str(rdate):>12} ${amt:>10.2f} {cat:>20} {vendor[:40]}")

if not to_fix:
    print("\n   No receipts need recategorization!")
else:
    print(f"\n2. Updating {len(to_fix)} receipts to category 'general_journal'...")
    
    # Update category
    cur.execute("""
        UPDATE receipts
        SET category = 'general_journal'
        WHERE (
            vendor_name ILIKE '%general journal%' 
            OR vendor_name ILIKE '%gen j%'
            OR vendor_name ILIKE 'gj %'
            OR description ILIKE '%general journal%'
            OR description ILIKE '%gen j%'
            OR description ILIKE 'gj %'
        )
        AND category != 'general_journal'
    """)
    
    updated = cur.rowcount
    print(f"   Updated: {updated} receipts")
    
    conn.commit()
    print(f"\n✓ Changes committed to database")

# Show updated category breakdown
print(f"\n3. Updated category breakdown:")
cur.execute("""
    SELECT 
        category,
        COUNT(*) as count,
        SUM(gross_amount) as total
    FROM receipts
    WHERE mapped_bank_account_id = 2
    AND created_from_banking = TRUE
    GROUP BY category
    ORDER BY total DESC
""")

for row in cur.fetchall():
    cat, count, total = row
    print(f"   {cat:30} | {count:5,} receipts | ${total:>12,.2f}")

print("\n" + "="*80)
print("RECOMMENDATIONS:")
print("="*80)
print("\n1. Update auto_create_receipts_from_all_banking.py:")
print("   Add to categorize_transaction() function:")
print("   ")
print("   # General Journal entries (accounting adjustments, not vendor invoices)")
print("   if any(x in desc_upper for x in ['GENERAL JOURNAL', 'GEN J', 'G J']):")
print("       return 'general_journal'")
print("")
print("2. Future imports will automatically categorize General Journal entries")
print("3. These entries represent accounting adjustments, not vendor expenses")
print("4. For tax purposes, verify if General Journal entries are deductible")

cur.close()
conn.close()
