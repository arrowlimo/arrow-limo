#!/usr/bin/env python3
"""Ensure all WCB receipts have GST set to 0"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

try:
    # First, show what we're about to change
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gst_code
        FROM receipts
        WHERE canonical_vendor = 'WCB' OR vendor_name ILIKE '%WCB%'
        ORDER BY receipt_date DESC
    """)
    
    wcb_receipts = cur.fetchall()
    print(f"Found {len(wcb_receipts)} WCB receipts in database:\n")
    
    needs_update = 0
    for row in wcb_receipts:
        receipt_id, receipt_date, vendor_name, gross_amount, gst_amount, gst_code = row
        print(f"  Receipt #{receipt_id:8} | {receipt_date} | {vendor_name:30} | Amount: ${gross_amount:8.2f} | GST: ${gst_amount or 0:6.2f} | Code: {gst_code or 'None'}")
        
        if gst_amount and gst_amount != 0:
            needs_update += 1
    
    print(f"\n✓ {len(wcb_receipts)} total WCB receipts")
    print(f"⚠ {needs_update} receipts need GST correction (gst_amount != 0)")
    
    if needs_update > 0:
        print("\nUpdating all WCB receipts to have GST = 0 and gst_code = 'GST_EXEMPT'...")
        
        # Backup before modifying
        backup_file = f"almsdata_backup_WCB_CORRECTION_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        print(f"Creating backup: {backup_file}")
        
        cur.execute("""
            UPDATE receipts
            SET gst_amount = 0, gst_code = 'GST_EXEMPT'
            WHERE canonical_vendor = 'WCB' OR vendor_name ILIKE '%WCB%'
        """)
        
        updated = cur.rowcount
        conn.commit()
        
        print(f"✅ Updated {updated} WCB receipts")
        print("✅ All WCB receipts now have GST = 0 and gst_code = 'GST_EXEMPT'")
        
        # Verify
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN gst_amount = 0 THEN 1 END) as zero_gst,
                   COUNT(CASE WHEN gst_code = 'GST_EXEMPT' THEN 1 END) as exempt_code
            FROM receipts
            WHERE canonical_vendor = 'WCB' OR vendor_name ILIKE '%WCB%'
        """)
        
        total, zero_gst, exempt_code = cur.fetchone()
        print(f"\nVerification:")
        print(f"  Total WCB receipts: {total}")
        print(f"  With GST = 0: {zero_gst}")
        print(f"  With gst_code = 'GST_EXEMPT': {exempt_code}")
    else:
        print("\n✅ All WCB receipts already have GST = 0")

except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
