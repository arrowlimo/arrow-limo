#!/usr/bin/env python3
"""
Verify 2014 leasing import and check database status.
"""

import os
import sys
import psycopg2

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
        port=os.getenv('DB_PORT', '5432')
    )

def verify_import():
    """Verify the 2014 leasing import."""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("VERIFYING 2014 LEASING IMPORT")
    print("=" * 40)
    
    # Check 2014 leasing import
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount), SUM(gst_amount)
        FROM receipts 
        WHERE source_system = '2014_Leasing_Import'
    """)
    
    import_result = cur.fetchone()
    
    if import_result and import_result[0] > 0:
        count, amount, gst = import_result
        print(f"[OK] 2014 Leasing Import:")
        print(f"   Records: {count}")
        print(f"   Amount: ${amount or 0:,.2f}")
        print(f"   GST: ${gst or 0:,.2f}")
    else:
        print("[FAIL] No 2014 leasing import found")
    
    # Check overall 2014 status
    cur.execute("""
        SELECT COUNT(*), SUM(gross_amount)
        FROM receipts 
        WHERE EXTRACT(YEAR FROM receipt_date) = 2014
    """)
    
    year_result = cur.fetchone()
    
    if year_result:
        count, amount = year_result
        print(f"\n📊 Total 2014 Records:")
        print(f"   Records: {count}")
        print(f"   Amount: ${amount or 0:,.2f}")
        
        if count > 1:
            print(f"   🎉 SUCCESS: 2014 now has substantial data!")
        else:
            print(f"   [WARN]  Still very low record count")
    
    # Check for constraint issues
    cur.execute("""
        SELECT source_hash, COUNT(*)
        FROM receipts 
        WHERE source_hash = 'AUTO_GENERATED'
        GROUP BY source_hash
        HAVING COUNT(*) > 1
    """)
    
    duplicate_hashes = cur.fetchall()
    
    if duplicate_hashes:
        print(f"\n[WARN]  Duplicate hash issue found:")
        for hash_val, count in duplicate_hashes:
            print(f"   Hash '{hash_val}': {count} duplicates")
    
    cur.close()
    conn.close()

def main():
    verify_import()

if __name__ == "__main__":
    main()