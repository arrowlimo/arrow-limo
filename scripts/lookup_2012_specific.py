#!/usr/bin/env python3
"""
Look up specific receipts from 2012 around the user-specified dates and amounts.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 70)
    print("2012 RECEIPT LOOKUP: ~$135 RUN'N ON EMPTY / FAS GAS")
    print("=" * 70)
    
    # Search around 09/05/2012 and 09/17/2012
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            category,
            parent_receipt_id,
            split_group_total,
            split_key,
            is_split_receipt,
            created_at
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            AND EXTRACT(MONTH FROM receipt_date) = 9
            AND (vendor_name ILIKE '%RUN''N ON EMPTY%' 
                 OR vendor_name ILIKE '%FAS GAS%')
            AND gross_amount BETWEEN 100 AND 170
        ORDER BY receipt_date, receipt_id
    """)
    
    rows = cur.fetchall()
    
    print(f"\nFound {len(rows)} matching receipts:\n")
    
    for receipt_id, receipt_date, vendor_name, gross_amount, description, category, parent_id, split_total, split_key, is_split, created_at in rows:
        print(f"ID {receipt_id:6d} | {receipt_date} | {vendor_name:20s} | ${gross_amount:8.2f}")
        print(f"  Category: {category}")
        print(f"  Description: {description}")
        print(f"  Parent receipt ID: {parent_id}")
        print(f"  Is split receipt: {is_split}")
        print(f"  Split group total: {split_total}")
        print(f"  Split key: {split_key}")
        print(f"  Created: {created_at}")
        print()
    
    # Also search by exact date ranges
    print("\n" + "=" * 70)
    print("ALL RUN'N ON EMPTY / FAS GAS around 09/05 - 09/17:")
    print("=" * 70 + "\n")
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            description,
            parent_receipt_id,
            is_split_receipt
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            AND receipt_date BETWEEN '2012-09-03' AND '2012-09-20'
            AND (vendor_name ILIKE '%RUN''N ON EMPTY%' 
                 OR vendor_name ILIKE '%FAS GAS%')
        ORDER BY receipt_date, receipt_id
    """)
    
    rows = cur.fetchall()
    
    for receipt_id, receipt_date, vendor_name, gross_amount, description, parent_id, is_split in rows:
        parent_status = f"[CHILD OF {parent_id}]" if parent_id else "[PARENT]" if is_split else "[STANDALONE]"
        print(f"ID {receipt_id:6d} | {receipt_date} | {vendor_name:20s} | ${gross_amount:8.2f} {parent_status}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    if conn:
        conn.close()
    exit(1)
