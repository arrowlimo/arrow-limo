#!/usr/bin/env python3
"""
Apply vendor name cleanup suggestions from Excel to database.
"""

import psycopg2
import pandas as pd
import re

# Read the Excel file
excel_file = r"l:\limo\reports\UNKNOWN_vendors_20251221_151046.xlsx"
print("=" * 80)
print("APPLYING VENDOR NAME CLEANUP")
print("=" * 80)

df = pd.read_excel(excel_file, sheet_name='Receipt Vendors')
print(f"\nLoaded {len(df)} vendors from Excel")

# Extract clean suggestions (exclude comments in parentheses)
changes = []

for idx, row in df.iterrows():
    suggested = row['Column1'] if 'Column1' in row and pd.notna(row['Column1']) else None
    current = row['Vendor Name'] if pd.notna(row['Vendor Name']) else None
    
    if suggested and current:
        suggested_clean = str(suggested).strip()
        current_clean = str(current).strip()
        
        # Skip if it's a comment (starts with parenthesis)
        if suggested_clean.startswith('('):
            continue
            
        # Remove anything after " (" including the parenthesis
        if '(' in suggested_clean:
            suggested_clean = suggested_clean.split('(')[0].strip()
        
        # Skip if empty after cleaning
        if not suggested_clean:
            continue
            
        # Skip if same as current
        if suggested_clean.upper() == current_clean.upper():
            continue
        
        # Skip obviously bad suggestions
        if suggested_clean.endswith('T') and not current_clean.endswith('T'):
            # Likely a typo (DEPOSITT, LIQUORT, etc.)
            continue
            
        changes.append({
            'from': current_clean,
            'to': suggested_clean,
            'row': idx
        })

print(f"\nProcessed {len(changes)} valid vendor name changes")

# Show first 30
print("\nFirst 30 changes:")
for i, change in enumerate(changes[:30]):
    print(f"  {i+1:3}. '{change['from'][:40]}' → '{change['to'][:40]}'")

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

print("\n" + "=" * 80)
print("APPLYING CHANGES TO DATABASE")
print("=" * 80)

updated_count = 0
failed = []

for change in changes:
    try:
        # Update receipts
        cur.execute("""
            UPDATE receipts
            SET vendor_name = %s
            WHERE vendor_name = %s
        """, (change['to'], change['from']))
        
        count = cur.rowcount
        if count > 0:
            updated_count += count
            if count > 100 or updated_count < 30:
                print(f"✅ Updated {count:4} receipts: '{change['from'][:35]}' → '{change['to'][:35]}'")
        
    except Exception as e:
        failed.append({'change': change, 'error': str(e)})
        print(f"❌ Failed: '{change['from'][:30]}' - {e}")

# Commit changes
conn.commit()

print(f"\n✅ COMMITTED: {updated_count} receipts updated")
print(f"   Applied: {len(changes) - len(failed)} changes")
print(f"   Failed: {len(failed)} changes")

if failed:
    print("\nFailed changes:")
    for f in failed[:10]:
        print(f"  '{f['change']['from'][:30]}' → '{f['change']['to'][:30]}'")

# Also handle Point of Sale USD transactions
print("\n" + "=" * 80)
print("EXTRACTING VENDORS FROM POINT OF SALE USD TRANSACTIONS")
print("=" * 80)

cur.execute("""
    SELECT 
        receipt_id,
        vendor_name,
        description
    FROM receipts
    WHERE vendor_name LIKE 'POINT OF SALE - VISA DEBIT INTL%'
       OR vendor_name LIKE 'POINT OF SALE - VISA DEB%RETAIL PURCHASE%'
    LIMIT 50
""")

pos_usd = cur.fetchall()
print(f"\nFound {len(pos_usd)} Point of Sale USD transactions")

if pos_usd:
    print("\nExamples:")
    for r_id, vendor, desc in pos_usd[:10]:
        print(f"  {vendor[:60]}")
    
    # Extract vendor from description
    pos_updates = 0
    for r_id, vendor, desc in pos_usd:
        # Try to extract vendor name from description or vendor field
        # Pattern: POINT OF SALE - VISA DEBIT INTL VISA DEB RETAIL PURCHASE WIX.COM
        match = re.search(r'RETAIL PURCHASE\s+([A-Z0-9\.]+)', vendor)
        if match:
            extracted_vendor = match.group(1).strip()
            
            # Clean up vendor name
            if '.' in extracted_vendor:
                # It's a domain like WIX.COM, 1AND1.COM
                extracted_vendor = extracted_vendor.split('.')[0]
            
            # Update
            cur.execute("""
                UPDATE receipts
                SET vendor_name = %s
                WHERE receipt_id = %s
            """, (extracted_vendor, r_id))
            
            pos_updates += 1
    
    conn.commit()
    print(f"\n✅ Updated {pos_updates} Point of Sale USD transactions")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("FINAL SUMMARY")
print("=" * 80)
print(f"\nVendor names updated: {updated_count}")
print(f"Point of Sale USD updated: {pos_updates if pos_usd else 0}")
print(f"Total receipts modified: {updated_count + (pos_updates if pos_usd else 0)}")

print("\n✅ COMPLETE")
