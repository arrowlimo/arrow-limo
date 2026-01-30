#!/usr/bin/env python3
"""Analyze 2012 Excel file for duplicates marked by user, then delete from database."""

import pandas as pd
import psycopg2
import os
from datetime import datetime
from difflib import SequenceMatcher

# Load the Excel file
excel_file = r'L:\limo\2012_Banking_Receipts_Reconciliation_20251204_221051.xlsx'
print("="*70)
print("ANALYZING 2012 EXCEL FILE FOR DUPLICATES")
print("="*70)
print(f"File: {excel_file}")
print()

# Read the Receipts worksheet
df = pd.read_excel(excel_file, sheet_name='Receipts 2012')
print(f"Loaded {len(df)} receipts from Excel")
print()

# Sort by date, then amount, then vendor
df_sorted = df.sort_values(['Date', 'Gross Amount', 'Vendor'], na_position='last')

# Check for user-marked duplicates (tagged or in red)
if 'Notes' in df.columns or 'Description' in df.columns:
    note_col = 'Notes' if 'Notes' in df.columns else 'Description'
    marked_duplicates = df_sorted[
        df_sorted[note_col].astype(str).str.contains('duplicate', case=False, na=False)
    ]
    print(f"Found {len(marked_duplicates)} receipts marked as 'duplicate' in {note_col}")
    print()

# Find potential duplicates using fuzzy matching
def fuzzy_match(s1, s2, threshold=0.85):
    """Return True if strings match above threshold."""
    if pd.isna(s1) or pd.isna(s2):
        return False
    return SequenceMatcher(None, str(s1).upper(), str(s2).upper()).ratio() >= threshold

def is_nsf_transaction(vendor, description):
    """Check if this is an NSF-related transaction that should not be treated as duplicate."""
    if pd.isna(vendor) and pd.isna(description):
        return False
    
    nsf_keywords = ['NSF', 'BOUNCE', 'NON-SUFFICIENT', 'REVERSAL', 'CORRECTION', 'CHARGE BACK']
    text = f"{str(vendor)} {str(description)}".upper()
    return any(keyword in text for keyword in nsf_keywords)

print("Finding duplicate groups (same date + amount + similar vendor)...")
print("WARNING: NSF transactions will be EXCLUDED from duplicate detection")
print()

duplicate_groups = []
seen_indices = set()

for i in range(len(df_sorted)):
    if i in seen_indices:
        continue
    
    row = df_sorted.iloc[i]
    date = row['Date']
    amount = row['Gross Amount']
    vendor = row['Vendor']
    receipt_id = row['Receipt ID']
    description = row.get('Description', '')
    
    # Skip NSF transactions entirely
    if is_nsf_transaction(vendor, description):
        seen_indices.add(i)
        continue
    
    # Find all rows with same date and amount
    group = []
    for j in range(i, len(df_sorted)):
        if j in seen_indices:
            continue
        
        other_row = df_sorted.iloc[j]
        other_date = other_row['Date']
        other_amount = other_row['Gross Amount']
        other_vendor = other_row['Vendor']
        other_id = other_row['Receipt ID']
        other_description = other_row.get('Description', '')
        
        # Skip NSF transactions
        if is_nsf_transaction(other_vendor, other_description):
            seen_indices.add(j)
            continue
        
        # If date or amount differs, we've moved past this group
        if other_date != date or abs(other_amount - amount) > 0.01:
            break
        
        # Check vendor fuzzy match
        if fuzzy_match(vendor, other_vendor, threshold=0.85):
            group.append({
                'receipt_id': other_id,
                'date': other_date,
                'vendor': other_vendor,
                'amount': other_amount,
                'index': j
            })
            seen_indices.add(j)
    
    if len(group) > 1:
        duplicate_groups.append(group)

print(f"Found {len(duplicate_groups)} duplicate groups with fuzzy vendor matching")
print()

# Show duplicate groups
print("DUPLICATE GROUPS FOUND:")
print("="*70)

total_to_delete = 0
receipts_to_keep = []
receipts_to_delete = []

for idx, group in enumerate(duplicate_groups, 1):  # Show all groups
    print(f"\nGroup {idx}: {len(group)} duplicates")
    for i, item in enumerate(group):
        marker = "KEEP" if i == 0 else "DELETE"
        receipt_id = int(item['receipt_id']) if not pd.isna(item['receipt_id']) else 0
        print(f"  [{marker}] ID: {receipt_id:6d} | {item['date']} | ${item['amount']:10,.2f} | {item['vendor'][:40]}")
        
        if i == 0:
            receipts_to_keep.append(receipt_id)
        else:
            receipts_to_delete.append(receipt_id)
            total_to_delete += 1

print()
print("="*70)
print(f"SUMMARY: {total_to_delete} duplicate receipts identified for deletion")
print(f"         {len(receipts_to_keep)} unique receipts to keep")
print("="*70)
print()

# Connect to database
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    database=os.getenv('DB_NAME', 'almsdata')
)
cur = conn.cursor()

# Verify receipt IDs exist in database
print("Verifying receipt IDs in database...")
if receipts_to_delete:
    cur.execute("""
        SELECT receipt_id FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (receipts_to_delete,))
    
    found_ids = {row[0] for row in cur.fetchall()}
    missing_ids = set(receipts_to_delete) - found_ids
    
    if missing_ids:
        print(f"WARNING: {len(missing_ids)} receipt IDs not found in database:")
        for rid in list(missing_ids)[:10]:
            print(f"    {rid}")
    
    print(f"Verified {len(found_ids)} receipt IDs exist in database")
    print()

# Ask for confirmation
print("="*70)
print("READY TO DELETE")
print("="*70)
print(f"This will DELETE {len(found_ids)} duplicate receipts from the database")
print(f"A backup will be created first: receipts_excel_duplicates_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
print()

response = input("Proceed with deletion? (yes/no): ").strip().lower()

if response == 'yes':
    # Create backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_table = f'receipts_excel_duplicates_backup_{timestamp}'
    
    print(f"\nCreating backup: {backup_table}")
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (list(found_ids),))
    conn.commit()
    print(f"Backed up {cur.rowcount} receipts")
    
    # Delete duplicates
    print(f"\nDeleting {len(found_ids)} duplicate receipts...")
    cur.execute("""
        DELETE FROM receipts
        WHERE receipt_id = ANY(%s)
    """, (list(found_ids),))
    deleted_count = cur.rowcount
    conn.commit()
    
    print(f"Successfully deleted {deleted_count} duplicate receipts")
    print()
    print("="*70)
    print("NEXT STEPS:")
    print("  1. Regenerate Excel: python scripts/reconcile_2012_banking_receipts_to_excel.py")
    print("  2. Review the new Excel file to confirm duplicates are gone")
    print("="*70)
else:
    print("\nDeletion cancelled")

conn.close()
