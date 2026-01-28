#!/usr/bin/env python3
"""
Fix spelling typos and research commented vendors from Excel.
"""

import psycopg2
import pandas as pd
import re

# Read the Excel file
excel_file = r"l:\limo\reports\UNKNOWN_vendors_20251221_151046.xlsx"
print("=" * 80)
print("FIXING SPELLING TYPOS AND RESEARCHING VENDORS")
print("=" * 80)

df = pd.read_excel(excel_file, sheet_name='Receipt Vendors')

# Step 1: Fix spelling typos that were skipped
print("\n1. FIXING SPELLING TYPOS")
print("-" * 80)

typo_fixes = []

for idx, row in df.iterrows():
    suggested = row['Column1'] if 'Column1' in row and pd.notna(row['Column1']) else None
    current = row['Vendor Name'] if pd.notna(row['Vendor Name']) else None
    
    if not suggested or not current:
        continue
    
    suggested_clean = str(suggested).strip()
    current_clean = str(current).strip()
    
    # Skip comments
    if suggested_clean.startswith('('):
        continue
    
    # Extract the part before any comment
    if '(' in suggested_clean:
        suggested_clean = suggested_clean.split('(')[0].strip()
    
    # Find typos that end with extra T
    if suggested_clean.endswith('T') and not current_clean.endswith('T'):
        # It's a typo - fix it
        correct_name = suggested_clean[:-1]  # Remove the T
        typo_fixes.append({
            'from': current_clean,
            'to': correct_name,
            'typo': suggested_clean
        })

print(f"Found {len(typo_fixes)} spelling typos to fix:")
for fix in typo_fixes[:20]:
    print(f"  '{fix['from'][:35]}' → '{fix['to'][:35]}' (was: {fix['typo']})")

# Step 2: Extract comments for research
print("\n\n2. EXTRACTING COMMENTS FOR RESEARCH")
print("-" * 80)

research_items = []

for idx, row in df.iterrows():
    suggested = row['Column1'] if 'Column1' in row and pd.notna(row['Column1']) else None
    current = row['Vendor Name'] if pd.notna(row['Vendor Name']) else None
    
    if not suggested or not current:
        continue
    
    suggested_str = str(suggested).strip()
    
    # Look for comments in parentheses
    if '(' in suggested_str:
        parts = suggested_str.split('(', 1)
        vendor_suggestion = parts[0].strip()
        comment = '(' + parts[1] if len(parts) > 1 else ''
        
        research_items.append({
            'vendor': str(current).strip(),
            'suggestion': vendor_suggestion,
            'comment': comment,
            'row': idx
        })

print(f"Found {len(research_items)} items with comments:")
for item in research_items[:30]:
    print(f"\n  Vendor: {item['vendor'][:40]}")
    print(f"  Suggestion: {item['suggestion'][:40]}")
    print(f"  Comment: {item['comment'][:60]}")

# Step 3: Research vendors by checking banking descriptions
print("\n\n3. RESEARCHING VENDORS IN DATABASE")
print("-" * 80)

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

# Research each item with a comment
print("\nLooking up original banking descriptions...\n")

for item in research_items[:50]:  # First 50
    vendor = item['vendor']
    
    # Find receipts with this vendor
    cur.execute("""
        SELECT 
            r.receipt_id,
            r.description,
            r.receipt_date,
            r.gross_amount,
            b.description as banking_desc,
            b.vendor_extracted as banking_vendor
        FROM receipts r
        LEFT JOIN banking_receipt_matching_ledger m ON r.receipt_id = m.receipt_id
        LEFT JOIN banking_transactions b ON m.banking_transaction_id = b.transaction_id
        WHERE r.vendor_name = %s
        LIMIT 5
    """, (vendor,))
    
    results = cur.fetchall()
    
    if results:
        print(f"\n{'='*80}")
        print(f"VENDOR: {vendor}")
        print(f"Comment: {item['comment']}")
        print(f"\nOriginal banking descriptions:")
        
        for r_id, r_desc, r_date, r_amt, b_desc, b_vendor in results:
            print(f"  {r_date} | ${r_amt:>10.2f}")
            if b_desc:
                print(f"    Banking: {b_desc[:70]}")
            if b_vendor:
                print(f"    Vendor:  {b_vendor}")
            if r_desc:
                print(f"    Receipt: {r_desc[:70]}")

# Step 4: Apply typo fixes
print("\n\n" + "=" * 80)
print("4. APPLYING SPELLING CORRECTIONS")
print("=" * 80)

updated = 0
for fix in typo_fixes:
    cur.execute("""
        UPDATE receipts
        SET vendor_name = %s
        WHERE vendor_name = %s
    """, (fix['to'], fix['from']))
    
    count = cur.rowcount
    if count > 0:
        updated += count
        print(f"✅ Fixed {count:3} receipts: '{fix['from'][:30]}' → '{fix['to'][:30]}'")

conn.commit()
print(f"\n✅ COMMITTED: {updated} receipts with spelling corrections")

cur.close()
conn.close()

print("\n✅ COMPLETE")
