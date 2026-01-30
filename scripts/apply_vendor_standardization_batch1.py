#!/usr/bin/env python
"""Apply vendor standardization batch 1: FAS GAS, CENTEX, COOP, WINE AND BEYOND, LIQUOR BARN, LBG'S."""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("\n" + "="*120)
print("VENDOR STANDARDIZATION - BATCH 1")
print("="*120)

try:
    # GROUP 1: FAS GAS (already standardized, just set canonical_vendor)
    print("\nGROUP 1: FAS GAS")
    print("-" * 100)
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'FAS GAS'
        WHERE UPPER(vendor_name) LIKE 'FAS%GAS%' OR UPPER(vendor_name) LIKE 'FASGAS%'
        RETURNING receipt_id, vendor_name
    """)
    updated = cur.fetchall()
    print(f"  ✓ Updated {len(updated)} receipts to canonical_vendor='FAS GAS'")
    
    # GROUP 2: CENTEX (standardize all variants)
    print("\nGROUP 2: CENTEX")
    print("-" * 100)
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'CENTEX'
        WHERE UPPER(vendor_name) LIKE 'CENTEX%' OR UPPER(vendor_name) LIKE '%CENTEX%'
        RETURNING receipt_id, vendor_name
    """)
    updated = cur.fetchall()
    print(f"  ✓ Updated {len(updated)} receipts to canonical_vendor='CENTEX'")
    
    # GROUP 3: COOP - CO OPERATORS → CO-OP INSURANCE
    print("\nGROUP 3: COOP")
    print("-" * 100)
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'CO-OP INSURANCE'
        WHERE UPPER(vendor_name) = 'CO OPERATORS'
        RETURNING receipt_id, vendor_name
    """)
    updated = cur.fetchall()
    print(f"  ✓ Updated {len(updated)} receipts (CO OPERATORS → CO-OP INSURANCE)")
    
    # Set canonical for CO-OP
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'CO-OP'
        WHERE UPPER(vendor_name) = 'CO-OP' AND canonical_vendor IS NULL
        RETURNING receipt_id
    """)
    updated = cur.fetchall()
    print(f"  ✓ Set canonical_vendor='CO-OP' for {len(updated)} receipts")
    
    # Set canonical for CO-OP INSURANCE
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'CO-OP INSURANCE'
        WHERE UPPER(vendor_name) LIKE '%CO-OP INSURANCE%' AND canonical_vendor IS NULL
        RETURNING receipt_id
    """)
    updated = cur.fetchall()
    print(f"  ✓ Set canonical_vendor='CO-OP INSURANCE' for {len(updated)} receipts")
    
    # GROUP 4: WINE AND BEYOND (already standardized)
    print("\nGROUP 4: WINE AND BEYOND")
    print("-" * 100)
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'WINE AND BEYOND'
        WHERE UPPER(vendor_name) = 'WINE AND BEYOND'
        RETURNING receipt_id
    """)
    updated = cur.fetchall()
    print(f"  ✓ Updated {len(updated)} receipts to canonical_vendor='WINE AND BEYOND'")
    
    # GROUP 5: LIQUOR BARN (excluding LBG'S)
    print("\nGROUP 5: LIQUOR BARN")
    print("-" * 100)
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'LIQUOR BARN'
        WHERE (UPPER(vendor_name) LIKE 'LIQUOR BARN%' OR UPPER(vendor_name) LIKE '%LIQUOR BARN%')
          AND UPPER(vendor_name) != 'LBG''S'
        RETURNING receipt_id, vendor_name
    """)
    updated = cur.fetchall()
    print(f"  ✓ Updated {len(updated)} receipts to canonical_vendor='LIQUOR BARN'")
    
    # GROUP 6: LEAH'S BAR AND GRILL
    print("\nGROUP 6: LEAH'S BAR AND GRILL")
    print("-" * 100)
    cur.execute("""
        UPDATE receipts
        SET canonical_vendor = 'LEAH''S BAR AND GRILL'
        WHERE UPPER(vendor_name) = 'LBG''S'
        RETURNING receipt_id, vendor_name
    """)
    updated = cur.fetchall()
    print(f"  ✓ Updated {len(updated)} receipts (LBG'S → LEAH'S BAR AND GRILL)")
    
    # Commit transaction
    conn.commit()
    print("\n" + "="*120)
    print("✅ ALL UPDATES COMMITTED SUCCESSFULLY")
    print("="*120)
    
    # Summary report
    print("\nSUMMARY:")
    cur.execute("""
        SELECT canonical_vendor, COUNT(*) as cnt
        FROM receipts
        WHERE canonical_vendor IN ('FAS GAS', 'CENTEX', 'CO-OP', 'CO-OP INSURANCE', 
                                   'WINE AND BEYOND', 'LIQUOR BARN', 'LEAH''S BAR AND GRILL')
        GROUP BY canonical_vendor
        ORDER BY canonical_vendor
    """)
    for vendor, count in cur.fetchall():
        print(f"  {vendor:30s} → {count:4d} receipts")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ ERROR: {e}")
    print("Transaction rolled back")
    raise
finally:
    cur.close()
    conn.close()
