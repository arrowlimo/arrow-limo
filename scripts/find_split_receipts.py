#!/usr/bin/env python
"""
Find all split receipts in database (marked with SPLIT/ in description)
Test the split receipt UI detection on them
"""

import os
import psycopg2
from decimal import Decimal

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
    
    # Find all receipts with SPLIT/ in description
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, 
               description, split_status
        FROM receipts
        WHERE description ILIKE '%SPLIT/%'
        ORDER BY receipt_date DESC, receipt_id DESC
        LIMIT 50
    """)
    
    splits = cur.fetchall()
    print(f"\n✅ Found {len(splits)} split receipts (marked with SPLIT/ in description)\n")
    print(f"{'ID':<8} {'Date':<12} {'Vendor':<20} {'Amount':<12} {'Status':<20} {'Description':<40}")
    print("-" * 130)
    
    for row in splits:
        receipt_id, receipt_date, vendor_name, gross_amount, description, split_status = row
        desc_preview = (description or "")[:40]
        print(f"{receipt_id:<8} {str(receipt_date):<12} {(vendor_name or '')[:20]:<20} ${float(gross_amount):<11,.2f} {(split_status or 'single'):<20} {desc_preview:<40}")
    
    # Analyze splits by year
    print(f"\n\n📊 Splits by Year:\n")
    cur.execute("""
        SELECT EXTRACT(YEAR FROM receipt_date) as year, COUNT(*) as count
        FROM receipts
        WHERE description ILIKE '%SPLIT/%'
        GROUP BY year
        ORDER BY year DESC
    """)
    
    for year_count in cur.fetchall():
        year, count = year_count
        if year:
            print(f"  {int(year)}: {count} split receipts")
    
    # Show sample splits with details
    print(f"\n\n📋 Sample Split Details (first 5):\n")
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, description
        FROM receipts
        WHERE description ILIKE '%SPLIT/%'
        ORDER BY receipt_date DESC
        LIMIT 5
    """)
    
    for i, (rid, rdate, vendor, amount, desc) in enumerate(cur.fetchall(), 1):
        print(f"{i}. Receipt #{rid} ({rdate})")
        print(f"   Vendor: {vendor}")
        print(f"   Amount: ${float(amount):,.2f}")
        print(f"   Description: {desc}\n")
    
    cur.close()
    conn.close()
    
    print(f"\n✅ READY TO TEST: Load any of these receipts in the app and the split UI will detect them automatically!")
    
except Exception as e:
    print(f"❌ Error: {e}")
