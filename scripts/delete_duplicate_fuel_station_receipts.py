#!/usr/bin/env python3
"""
Delete duplicate FUEL STATION receipts (145318 and children).
Keep RUN'N ON EMPTY entries (145322, 145323, 140662) which are linked to banking 69336.
"""

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def main():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    print("=" * 100)
    print("DELETE DUPLICATE FUEL STATION RECEIPTS (145318-145321)")
    print("=" * 100)
    
    # Show what we're deleting
    print("\n📋 RECEIPTS TO DELETE:")
    print("-" * 100)
    
    to_delete = [145318, 145319, 145320, 145321]
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            parent_receipt_id,
            description
        FROM receipts
        WHERE receipt_id = ANY(%s)
        ORDER BY receipt_id
    """, (to_delete,))
    
    records = cur.fetchall()
    for rec in records:
        rid, rdate, vendor, amt, parent, desc = rec
        parent_str = f"(child of {parent})" if parent else "(parent)"
        print(f"  Receipt {rid:6} | {rdate} | {vendor:20} | ${amt:>10.2f} | {parent_str}")
    
    # Show what we're keeping
    print("\n✅ RECEIPTS TO KEEP (RUN'N ON EMPTY - linked to Banking 69336):")
    print("-" * 100)
    
    to_keep = [145322, 145323, 140662]
    
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            banking_transaction_id,
            description
        FROM receipts
        WHERE receipt_id = ANY(%s)
        ORDER BY receipt_id
    """, (to_keep,))
    
    records = cur.fetchall()
    total_kept = 0
    for rec in records:
        rid, rdate, vendor, amt, bank_id, desc = rec
        total_kept += amt
        print(f"  Receipt {rid:6} | {rdate} | {vendor:20} | ${amt:>10.2f} | Banking {bank_id}")
    
    print(f"\n  TOTAL KEPT: ${total_kept:.2f}")
    
    # Perform deletion
    print("\n" + "=" * 100)
    print("DELETING...")
    print("=" * 100)
    
    try:
        # Delete children first (145319, 145320, 145321)
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id IN (145319, 145320, 145321)
        """)
        deleted_children = cur.rowcount
        print(f"✓ Deleted {deleted_children} child receipts (145319-145321)")
        
        # Delete parent (145318)
        cur.execute("""
            DELETE FROM receipts
            WHERE receipt_id = 145318
        """)
        deleted_parent = cur.rowcount
        print(f"✓ Deleted {deleted_parent} parent receipt (145318)")
        
        conn.commit()
        
        print(f"\n✅ DELETION COMPLETE: {deleted_parent + deleted_children} total receipts removed")
        print(f"   Remaining: 3 RUN'N ON EMPTY receipts totaling $135.00")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        return False
    
    finally:
        cur.close()
        conn.close()
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
