#!/usr/bin/env python3
"""
Find synthetic full-total parents in 2012 receipts.

Synthetic parent = receipt amount equals the sum of other receipts with same split_group_total/split_key
These are redundant totaling receipts and should be deleted.
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
    print("2012 SYNTHETIC PARENT RECEIPT DETECTION")
    print("=" * 70)
    
    # Strategy 1: Find by split_group_total (if set)
    print("\n1. Checking for receipts grouped by split_group_total:")
    cur.execute("""
        SELECT 
            split_group_total,
            COUNT(*) as group_count,
            SUM(gross_amount) as sum_amount,
            MAX(gross_amount) as max_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012 
            AND split_group_total IS NOT NULL
        GROUP BY split_group_total
        HAVING COUNT(*) > 1
        ORDER BY split_group_total DESC
        LIMIT 20
    """)
    
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} split groups in 2012:")
        for split_total, group_count, sum_amount, max_amount in rows:
            print(f"   Split total ${split_total:10.2f} | {group_count} receipts | Sum: ${sum_amount:10.2f} | Max: ${max_amount:10.2f}")
            
            if abs(float(split_total) - float(max_amount)) < 0.01:
                print(f"      🔴 SYNTHETIC: One receipt (${ max_amount:.2f}) equals the group total")
    else:
        print("   No split_group_total found in 2012")
    
    # Strategy 2: Find by split_key
    print("\n2. Checking for receipts grouped by split_key:")
    cur.execute("""
        SELECT 
            split_key,
            COUNT(*) as group_count,
            SUM(gross_amount) as sum_amount,
            MAX(gross_amount) as max_amount
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012 
            AND split_key IS NOT NULL
        GROUP BY split_key
        HAVING COUNT(*) > 1
        ORDER BY split_key DESC
        LIMIT 20
    """)
    
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} split groups in 2012:")
        for split_key, group_count, sum_amount, max_amount in rows:
            print(f"   Split key '{split_key}' | {group_count} receipts | Sum: ${sum_amount:10.2f} | Max: ${max_amount:10.2f}")
            
            if sum_amount and max_amount and abs(float(sum_amount) - float(max_amount)) < 0.01:
                print(f"      🔴 SYNTHETIC: One receipt equals group total")
    else:
        print("   No split_key found in 2012")
    
    # Strategy 3: Look for same vendor/date with multiple amounts that sum
    print("\n3. Checking for date-vendor groups with potential synthetic parents:")
    cur.execute("""
        SELECT 
            receipt_date,
            vendor_name,
            COUNT(*) as count,
            SUM(gross_amount) as total_amount,
            MAX(gross_amount) as max_receipt,
            STRING_AGG(DISTINCT CAST(gross_amount AS VARCHAR), ', ') as amounts
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012 
        GROUP BY receipt_date, vendor_name
        HAVING COUNT(*) > 1
        ORDER BY total_amount DESC
        LIMIT 20
    """)
    
    rows = cur.fetchall()
    if rows:
        print(f"   Found {len(rows)} multi-receipt vendor groups on same day:")
        for receipt_date, vendor_name, count, total_amount, max_receipt, amounts in rows:
            if total_amount is None or max_receipt is None:
                continue
            print(f"   {receipt_date} | {vendor_name[:25]:25s} | {count} items | Total: ${total_amount:10.2f}")
            print(f"      Amounts: {amounts}")
            
            # Check if one receipt equals sum of others
            if count >= 2 and abs(float(max_receipt) * 2 - float(total_amount)) < 0.01:
                print(f"      🔴 POSSIBLE SYNTHETIC: Max receipt (${max_receipt:.2f}) may equal sum of others")
    else:
        print("   No multi-receipt groups found")
    
    print("\n" + "=" * 70)
    print("Next step: Get detailed list of suspected synthetic parents")
    print("=" * 70)
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    if conn:
        conn.close()
    exit(1)
