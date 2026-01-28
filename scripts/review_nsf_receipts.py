#!/usr/bin/env python3
"""
Review NSF receipts before recategorization.
"""

import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Find NSF receipts
    cur.execute("""
        SELECT id, receipt_date, vendor_name, gross_amount, 
               category, description, source_reference
        FROM receipts
        WHERE category = 'nsf_event' 
           OR description ILIKE '%nsf%'
           OR vendor_name ILIKE '%nsf%'
        ORDER BY receipt_date
    """)
    
    results = cur.fetchall()
    
    print(f"\nNSF Receipts Found: {len(results)}")
    print("=" * 120)
    
    for row in results:
        rid, date, vendor, amount, cat, desc, source_ref = row
        vendor_str = vendor[:40] if vendor else "None"
        desc_str = desc[:60] if desc else "None"
        
        print(f"ID: {rid:6} | Date: {date} | Vendor: {vendor_str:40} | Amount: ${amount:8.2f}")
        print(f"         Category: {cat:20} | Source: {source_ref}")
        print(f"         Description: {desc_str}")
        print()
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
