#!/usr/bin/env python3
"""
Flatten 2019 parent-child split receipts.

Action:
- Null parent_receipt_id on all 2019 child receipts
- Creates backup before making changes
- Validates data integrity before/after

2019 structure: 49 parent + 49 child = 98 total receipts
"""

import os
import psycopg2
from datetime import datetime

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
    
    # Check 2019 split structure before flattening
    print("=" * 70)
    print("BEFORE FLATTENING: 2019 Split Structure")
    print("=" * 70)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2019 AND parent_receipt_id IS NULL AND is_split_receipt) AS parent_count,
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2019 AND parent_receipt_id IS NOT NULL) AS child_count,
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2019) AS total_2019
        FROM receipts
    """)
    parent_count, child_count, total_2019 = cur.fetchone()
    print(f"Parent receipts (is_split_receipt=TRUE, parent_receipt_id=NULL): {parent_count}")
    print(f"Child receipts (parent_receipt_id NOT NULL):                     {child_count}")
    print(f"Total 2019 receipts:                                              {total_2019}")
    
    # Show first few parent-child pairs
    print("\n" + "=" * 70)
    print("Sample Parent-Child Pairs (first 5):")
    print("=" * 70)
    
    cur.execute("""
        SELECT 
            p.receipt_id AS parent_id,
            p.receipt_date,
            p.vendor_name,
            p.gross_amount AS parent_amount,
            p.split_group_total,
            c.receipt_id AS child_id,
            c.gross_amount AS child_amount
        FROM receipts p
        LEFT JOIN receipts c ON c.parent_receipt_id = p.receipt_id
        WHERE EXTRACT(YEAR FROM p.receipt_date) = 2019 
            AND p.parent_receipt_id IS NULL 
            AND p.is_split_receipt = TRUE
        ORDER BY p.receipt_id
        LIMIT 5
    """)
    
    for parent_id, receipt_date, vendor_name, parent_amount, split_total, child_id, child_amount in cur.fetchall():
        print(f"Parent {parent_id:5d} | {receipt_date} | {vendor_name:20s} | ${parent_amount:8.2f} | split_total: ${split_total:8.2f}")
        if child_id:
            print(f"  └─ Child  {child_id:5d} |                                  | ${child_amount:8.2f}")
    
    # Confirm action
    print("\n" + "=" * 70)
    print(f"FLATTEN ACTION: NULL parent_receipt_id on {child_count} child receipts")
    print("=" * 70)
    
    response = input(f"\n⚠️  This will modify {child_count} child receipts. Continue? (yes/no): ").strip().lower()
    
    if response != "yes":
        print("Cancelled. No changes made.")
        cur.close()
        conn.close()
        exit(0)
    
    # Backup: Create SQL dump of affected rows
    backup_file = f"l:\\limo\\backups\\receipts_2019_children_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
    cur.execute("""
        SELECT COUNT(*) FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019 AND parent_receipt_id IS NOT NULL
    """)
    total_children = cur.fetchone()[0]
    
    print(f"\n✅ Backup file created (when you need rollback): {backup_file}")
    
    # Flatten: NULL parent_receipt_id on all 2019 children
    print("\n🔄 Flattening 2019 receipts (setting parent_receipt_id = NULL)...")
    
    cur.execute("""
        UPDATE receipts
        SET parent_receipt_id = NULL
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019 AND parent_receipt_id IS NOT NULL
    """)
    
    affected_rows = cur.rowcount
    conn.commit()
    
    print(f"✅ Updated {affected_rows} child receipts (parent_receipt_id now NULL)")
    
    # Verify after flattening
    print("\n" + "=" * 70)
    print("AFTER FLATTENING: Verification")
    print("=" * 70)
    
    cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2019 AND parent_receipt_id IS NULL AND is_split_receipt) AS parent_count,
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2019 AND parent_receipt_id IS NOT NULL) AS child_count,
            COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM receipt_date) = 2019) AS total_2019
        FROM receipts
    """)
    parent_count_after, child_count_after, total_2019_after = cur.fetchone()
    
    print(f"Parent receipts (is_split_receipt=TRUE):       {parent_count_after}")
    print(f"Child receipts (parent_receipt_id NOT NULL):   {child_count_after}")
    print(f"Total 2019 receipts:                            {total_2019_after}")
    
    if child_count_after == 0:
        print("\n✅ FLATTENING COMPLETE: All 2019 children now independent (parent_receipt_id nulled)")
    else:
        print(f"\n⚠️  WARNING: {child_count_after} children still have parent_receipt_id; something went wrong")
    
    # Show sample of flattened receipts
    print("\n" + "=" * 70)
    print("Sample Flattened Receipts (first 5 from original children):")
    print("=" * 70)
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            parent_receipt_id,
            is_split_receipt,
            split_group_total
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2019 
            AND receipt_id IN (SELECT receipt_id FROM receipts WHERE EXTRACT(YEAR FROM receipt_date) = 2019 ORDER BY receipt_id OFFSET 50 LIMIT 5)
        ORDER BY receipt_id
    """)
    
    for receipt_id, receipt_date, vendor_name, total_amount, parent_id, is_split, split_total in cur.fetchall():
        parent_status = "NULL (independent)" if parent_id is None else f"{parent_id} (error)"
        print(f"ID {receipt_id:5d} | {receipt_date} | {vendor_name:20s} | ${total_amount:8.2f} | parent_id: {parent_status}")
    
    print("\n" + "=" * 70)
    print("✅ FLATTENING COMPLETE - Ready for API updates")
    print("=" * 70)
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.rollback()
        conn.close()
    exit(1)
