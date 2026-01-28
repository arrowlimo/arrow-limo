#!/usr/bin/env python3
"""
Show all remaining driver/staff payment entries for review and consolidation.
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

try:
    # Get all driver/staff payment entries
    cur.execute("""
        SELECT vendor_name, 
               COUNT(*) as count, 
               SUM(gross_amount) as total_amount,
               gl_account_code,
               MIN(receipt_id) as sample_id
        FROM receipts
        WHERE (
            vendor_name ILIKE '%PAUL RICHARD%'
            OR vendor_name ILIKE '%PAUL MANSELL%'
            OR vendor_name ILIKE '%MICHAEL RICHARD%'
            OR vendor_name ILIKE '%MARK LINTON%'
            OR vendor_name ILIKE '%KEITH DIXON%'
            OR vendor_name ILIKE '%JEANNIE SHILLINGTON%'
            OR vendor_name ILIKE '%DAVE RICHARD%'
            OR vendor_name ILIKE '%JESSE GORDON%'
            OR vendor_name ILIKE '%STEPHEN MEEK%'
            OR vendor_name ILIKE '%TAMMY PETTITT%'
            OR vendor_name ILIKE '%KAREN%RICHARD%'
            OR vendor_name ILIKE '%ETRANSFER%'
            OR vendor_name ILIKE '%EMAIL TRANSFER%'
        )
        GROUP BY vendor_name, gl_account_code
        ORDER BY SUM(gross_amount) DESC
    """)
    
    results = cur.fetchall()
    
    print("\n" + "="*100)
    print("DRIVER/STAFF PAYMENT SUMMARY - REMAINING GL 6900 ENTRIES")
    print("="*100)
    
    total_count = 0
    total_amount = 0
    
    for vendor_name, count, total_amount_vendor, gl_code, sample_id in results:
        total_count += count
        total_amount += total_amount_vendor
        
        gl_label = gl_code if gl_code else "NULL"
        print(f"\n{vendor_name}")
        print(f"  Count: {count:,} receipts | Amount: ${total_amount_vendor:,.2f} | GL: {gl_label}")
        print(f"  Sample receipt: {sample_id}")
    
    print(f"\n{'='*100}")
    print(f"TOTAL DRIVER/STAFF PAYMENTS: {total_count:,} receipts (${total_amount:,.2f})")
    print(f"{'='*100}")
    
    # Now show top unidentified payment types
    print(f"\n{'='*100}")
    print("OTHER UNIDENTIFIED GL 6900 ENTRIES (Top 20)")
    print(f"{'='*100}\n")
    
    cur.execute("""
        SELECT vendor_name, COUNT(*) as count, SUM(gross_amount) as total
        FROM receipts
        WHERE gl_account_code = '6900'
        AND vendor_name NOT ILIKE '%PAUL%'
        AND vendor_name NOT ILIKE '%MICHAEL%'
        AND vendor_name NOT ILIKE '%MARK%'
        AND vendor_name NOT ILIKE '%KEITH%'
        AND vendor_name NOT ILIKE '%JEANNIE%'
        AND vendor_name NOT ILIKE '%DAVE%'
        AND vendor_name NOT ILIKE '%JESSE%'
        AND vendor_name NOT ILIKE '%STEPHEN%'
        AND vendor_name NOT ILIKE '%TAMMY%'
        AND vendor_name NOT ILIKE '%KAREN%'
        GROUP BY vendor_name
        ORDER BY SUM(gross_amount) DESC
        LIMIT 20
    """)
    
    other_results = cur.fetchall()
    for vendor_name, count, total in other_results:
        total_str = f"${total:>12,.2f}" if total else "NULL    "
        print(f"{vendor_name:<50} {count:>4} receipts  {total_str}")

finally:
    cur.close()
    conn.close()
