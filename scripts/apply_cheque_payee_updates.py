#!/usr/bin/env python
"""
Apply cheque payee updates from QuickBooks reconciliation PDF extraction.
Cleans up payee names and updates cheque_register table.
"""

import psycopg2
import os
import csv
import re
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def clean_payee_name(raw_payee):
    """
    Clean up payee name extracted from PDF.
    Removes trailing amounts and artifacts.
    """
    # Remove amount patterns at the end
    # Patterns: -123.45, -1,234.56, ~123.45, X-123.45
    payee = re.sub(r'\s+[~X-]?\s*-?\d{1,3}(?:,\d{3})*\.\d{2}\s*$', '', raw_payee)
    
    # Remove trailing dots and ellipsis
    payee = re.sub(r'\.{3,}\s*$', '', payee)
    
    # Remove trailing symbols
    payee = payee.rstrip('~X- «')
    
    # Clean up multiple spaces
    payee = re.sub(r'\s+', ' ', payee)
    
    return payee.strip()

def load_updates(csv_path):
    """Load payee updates from CSV"""
    updates = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            reg_id = int(row['cheque_register_id'])
            cheque_num = row['cheque_number']
            current = row['current_payee']
            new_payee_raw = row['new_payee']
            amount = Decimal(row['amount'])
            
            # Clean up payee name
            new_payee_clean = clean_payee_name(new_payee_raw)
            
            updates.append({
                'id': reg_id,
                'cheque_number': cheque_num,
                'current_payee': current,
                'new_payee_raw': new_payee_raw,
                'new_payee_clean': new_payee_clean,
                'amount': amount
            })
    
    return updates

def apply_updates(updates, cur, conn, dry_run=True):
    """Apply payee updates to database"""
    # Deduplicate by cheque_register_id (keep first occurrence)
    seen_ids = set()
    unique_updates = []
    
    for update in updates:
        if update['id'] not in seen_ids:
            seen_ids.add(update['id'])
            unique_updates.append(update)
    
    print(f"\nDeduplicating: {len(updates)} total → {len(unique_updates)} unique cheques")
    
    updated_count = 0
    
    for update in unique_updates:
        if not dry_run:
            cur.execute("""
                UPDATE cheque_register
                SET payee = %s
                WHERE id = %s
            """, (update['new_payee_clean'], update['id']))
            updated_count += 1
    
    if not dry_run:
        conn.commit()
    
    return updated_count

def main():
    csv_path = r'L:\limo\data\cheque_payee_updates_from_qb.csv'
    
    print("=" * 80)
    print("APPLY CHEQUE PAYEE UPDATES FROM QUICKBOOKS PDF")
    print("=" * 80)
    
    # Load updates
    print(f"\nLoading updates from: {csv_path}")
    updates = load_updates(csv_path)
    print(f"[OK] Loaded {len(updates)} payee updates")
    
    # Show sample of cleaned payees
    print("\n" + "=" * 80)
    print("SAMPLE CLEANED PAYEES (first 20)")
    print("=" * 80)
    
    for i, update in enumerate(updates[:20]):
        print(f"\n{i+1:2d}. Cheque #{update['cheque_number']} (ID:{update['id']}) | ${update['amount']:,.2f}")
        print(f"    Raw PDF:  {update['new_payee_raw']}")
        print(f"    Cleaned:  {update['new_payee_clean']}")
        if update['new_payee_raw'] != update['new_payee_clean']:
            print(f"    Changed: ✓")
    
    # Show duplicates (same cheque appearing multiple times)
    print("\n" + "=" * 80)
    print("CHECKING FOR DUPLICATES")
    print("=" * 80)
    
    cheque_counts = {}
    for update in updates:
        num = update['cheque_number']
        if num not in cheque_counts:
            cheque_counts[num] = []
        cheque_counts[num].append(update)
    
    duplicates = {k: v for k, v in cheque_counts.items() if len(v) > 1}
    
    if duplicates:
        print(f"\n[WARN] Found {len(duplicates)} cheques appearing multiple times:")
        for cheque_num, updates_list in list(duplicates.items())[:10]:
            print(f"\n  Cheque #{cheque_num} ({len(updates_list)} times):")
            for u in updates_list:
                print(f"    ID:{u['id']} | {u['new_payee_clean']} | ${u['amount']:,.2f}")
    else:
        print("[OK] No duplicates found")
    
    # DRY RUN
    print("\n" + "=" * 80)
    print("DRY RUN: APPLYING UPDATES")
    print("=" * 80)
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    updated_count = apply_updates(updates, cur, conn, dry_run=True)
    
    print(f"\nWould update {len(updates)} payee fields in cheque_register")
    
    # Show current state from database
    print("\n" + "=" * 80)
    print("CURRENT DATABASE STATE (sample)")
    print("=" * 80)
    
    sample_ids = [u['id'] for u in updates[:10]]
    cur.execute("""
        SELECT id, cheque_number, payee, amount
        FROM cheque_register
        WHERE id = ANY(%s)
        ORDER BY id
    """, (sample_ids,))
    
    print("\nCurrent payees in database:")
    for row in cur.fetchall():
        reg_id, cheque_num, current_payee, amount = row
        print(f"  ID:{reg_id} | Cheque #{cheque_num} | {current_payee or '(blank)'} | ${amount:,.2f}")
    
    cur.close()
    conn.close()
    
    # Instructions
    print("\n" + "=" * 80)
    print("TO APPLY UPDATES")
    print("=" * 80)
    print("\nReview the cleaned payees above, then run:")
    print("  python apply_cheque_payee_updates.py --write")
    print("\nThis will update all blank payees with QuickBooks data.")

if __name__ == '__main__':
    import sys
    
    if '--write' in sys.argv:
        print("\n[WARN] WRITE MODE ENABLED [WARN]")
        confirm = input("\nThis will update payees in the database. Continue? (yes/no): ")
        if confirm.lower() == 'yes':
            csv_path = r'L:\limo\data\cheque_payee_updates_from_qb.csv'
            updates = load_updates(csv_path)
            conn = get_db_connection()
            cur = conn.cursor()
            updated_count = apply_updates(updates, cur, conn, dry_run=False)
            cur.close()
            conn.close()
            print(f"\n[OK] Updated {updated_count} cheque payees")
        else:
            print("Cancelled")
    else:
        main()
