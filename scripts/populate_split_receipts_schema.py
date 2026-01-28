#!/usr/bin/env python3
"""
Populate parent/child split schema for receipts with SPLIT/ in description.

Business rules:
- Receipts with SPLIT/[amount] are components of one physical receipt
- Components with same date, vendor, and SPLIT total are grouped
- First component (usually largest) becomes parent
- Others reference parent via parent_receipt_id
"""

import psycopg2
from decimal import Decimal
from collections import defaultdict
import re

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

DRY_RUN = False  # Set to True for preview

def parse_split_amount(description):
    """Extract split total from SPLIT/[amount] pattern."""
    if not description:
        return None
    
    match = re.search(r'SPLIT/(\d+\.?\d*)', description, re.IGNORECASE)
    if match:
        return Decimal(match.group(1))
    return None

def group_split_receipts(receipts):
    """
    Group receipts by: receipt_date + vendor_name + split_total
    Returns dict: group_key -> [receipt_ids sorted by amount DESC]
    """
    groups = defaultdict(list)
    
    for receipt_id, receipt_date, vendor_name, gross_amount, description in receipts:
        split_total = parse_split_amount(description)
        if not split_total:
            continue
        
        # Create group key: date + vendor + split total
        group_key = f"{receipt_date}|{vendor_name}|{split_total}"
        groups[group_key].append({
            'receipt_id': receipt_id,
            'gross_amount': gross_amount,
            'split_total': split_total
        })
    
    # Sort each group by amount DESC (largest = parent)
    for group_key in groups:
        groups[group_key].sort(key=lambda x: x['gross_amount'], reverse=True)
    
    return groups

def main():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    print("=" * 80)
    print("POPULATE SPLIT RECEIPTS SCHEMA")
    print("=" * 80)
    
    # Find all receipts with SPLIT/ in description
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE description ILIKE '%split/%'
        AND exclude_from_reports = FALSE
        ORDER BY receipt_date, vendor_name, gross_amount DESC
    """)
    
    split_receipts = cur.fetchall()
    print(f"\nFound {len(split_receipts)} split receipts")
    
    if not split_receipts:
        print("✅ No split receipts to process")
        cur.close()
        conn.close()
        return
    
    # Group receipts by date + vendor + split total
    groups = group_split_receipts(split_receipts)
    
    print(f"Grouped into {len(groups)} physical receipts\n")
    
    # Process each group
    updates_made = 0
    parent_child_pairs = []
    
    for group_key, components in groups.items():
        date, vendor, split_total = group_key.split('|')
        
        if len(components) < 2:
            print(f"⚠️  Single component for {date} {vendor} SPLIT/{split_total} - skipping")
            continue
        
        # First (largest) is parent
        parent = components[0]
        children = components[1:]
        
        print(f"\n{date} | {vendor} | SPLIT/${split_total}")
        print(f"  Parent: Receipt #{parent['receipt_id']} (${parent['gross_amount']})")
        
        # Update parent fields
        if not DRY_RUN:
            cur.execute("""
                UPDATE receipts
                SET 
                    is_split_receipt = TRUE,
                    split_key = %s,
                    split_group_total = %s
                WHERE receipt_id = %s
            """, (group_key, split_total, parent['receipt_id']))
            updates_made += 1
        
        # Update children to reference parent
        for child in children:
            print(f"    Child: Receipt #{child['receipt_id']} (${child['gross_amount']})")
            
            if not DRY_RUN:
                cur.execute("""
                    UPDATE receipts
                    SET 
                        parent_receipt_id = %s,
                        is_split_receipt = TRUE,
                        split_key = %s,
                        split_group_total = %s
                    WHERE receipt_id = %s
                """, (parent['receipt_id'], group_key, split_total, child['receipt_id']))
                updates_made += 1
            
            parent_child_pairs.append({
                'parent_id': parent['receipt_id'],
                'child_id': child['receipt_id'],
                'date': date,
                'vendor': vendor,
                'split_total': split_total
            })
    
    if DRY_RUN:
        print("\n" + "=" * 80)
        print("DRY RUN - No changes made")
        print("=" * 80)
        print(f"Would update {len(groups)} groups with {sum(len(g) for g in groups.values())} receipts")
        conn.rollback()
    else:
        conn.commit()
        print("\n" + "=" * 80)
        print("✅ COMMIT SUCCESSFUL")
        print("=" * 80)
        print(f"Updated {updates_made} receipts")
        print(f"Created {len(parent_child_pairs)} parent-child relationships")
    
    # Verification query
    cur.execute("""
        SELECT 
            COUNT(*) as total_split,
            COUNT(CASE WHEN parent_receipt_id IS NULL THEN 1 END) as parents,
            COUNT(CASE WHEN parent_receipt_id IS NOT NULL THEN 1 END) as children
        FROM receipts
        WHERE is_split_receipt = TRUE
    """)
    
    total_split, parents, children = cur.fetchone()
    
    print("\nVERIFICATION:")
    print(f"  Total split receipts: {total_split}")
    print(f"  Parents: {parents}")
    print(f"  Children: {children}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
