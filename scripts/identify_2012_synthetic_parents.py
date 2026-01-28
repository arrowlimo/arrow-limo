#!/usr/bin/env python3
"""
Identify ALL synthetic parents in 2012 by checking if any receipt amount 
equals the sum of other receipts with the same date and vendor.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 70)
    print("2012 SYNTHETIC PARENT IDENTIFICATION")
    print("=" * 70)
    
    # Get all receipts from 2012 grouped by date and vendor
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            receipt_id,
            gross_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        ORDER BY receipt_date, vendor_name, gross_amount DESC
    """)
    
    all_receipts = cur.fetchall()
    
    # Group by date and vendor
    groups = {}
    for receipt_date, vendor_name, receipt_id, gross_amount in all_receipts:
        key = (receipt_date, vendor_name)
        if key not in groups:
            groups[key] = []
        groups[key].append((receipt_id, gross_amount))
    
    synthetic_parents = []
    
    # Check each group for synthetic parents
    for (receipt_date, vendor_name), receipts in groups.items():
        if len(receipts) < 2:
            continue
        
        # For each receipt, check if it equals sum of others
        for i, (parent_id, parent_amount) in enumerate(receipts):
            other_ids = [r[0] for j, r in enumerate(receipts) if j != i]
            other_sum = sum(r[1] for j, r in enumerate(receipts) if j != i)
            
            # If this receipt equals sum of all others, it's a synthetic parent
            if abs(float(parent_amount) - float(other_sum)) < 0.01 and other_sum > 0:
                synthetic_parents.append({
                    'receipt_id': parent_id,
                    'date': receipt_date,
                    'vendor': vendor_name,
                    'amount': parent_amount,
                    'child_count': len(other_ids),
                    'child_sum': other_sum,
                    'child_ids': other_ids
                })
    
    print(f"\nFound {len(synthetic_parents)} synthetic parent receipts in 2012:\n")
    
    total_amount_to_delete = 0
    for sp in synthetic_parents:
        print(f"Receipt ID {sp['receipt_id']:6d} | {sp['date']} | {sp['vendor'][:25]:25s}")
        print(f"   Amount: ${sp['amount']:10.2f} (synthetic total)")
        print(f"   Children: {sp['child_count']} receipts, sum = ${sp['child_sum']:10.2f}")
        print(f"   Child IDs: {sp['child_ids']}")
        print()
        total_amount_to_delete += float(sp['amount'])
    
    print("=" * 70)
    print(f"✅ ACTION: Delete {len(synthetic_parents)} synthetic parents")
    print(f"   Total amount in synthetic parents: ${total_amount_to_delete:10.2f}")
    print(f"   This will remove the over-count (receipts will still have children)")
    print("=" * 70)
    
    if synthetic_parents:
        print("\nSQL to delete synthetic parents:")
        print("BEGIN;")
        for sp in synthetic_parents:
            print(f"DELETE FROM receipts WHERE receipt_id = {sp['receipt_id']};")
        print("COMMIT;")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if conn:
        conn.close()
    exit(1)
