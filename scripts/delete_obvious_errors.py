#!/usr/bin/env python3
"""
DELETE OBVIOUSLY ERRONEOUS RECEIPTS

These 25 receipts are clear import errors/duplicates:
1. JOURNAL ENTRY (3 receipts) - Fake internal entries
2. HEFFNER NULL AMOUNT (19 receipts) - Duplicates with no amount
3. OPENING BALANCE (2 receipts) - Obsolete system entries
4. TELUS DUPLICATE (1 receipt) - Marked as [DUPLICATE - IGNORE]

SAFE TO DELETE - No business value, clear errors
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

deleted = {}

try:
    print("\n" + "="*100)
    print("DELETING OBVIOUS RECEIPT ERRORS")
    print("="*100)
    
    # 1. Delete JOURNAL ENTRY (Fake entries)
    print("\n1. Deleting JOURNAL ENTRY (Fake/duplicate entries)...")
    cur.execute("""
        DELETE FROM receipts
        WHERE vendor_name ILIKE 'JOURNAL ENTRY%'
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    je_results = cur.fetchall()
    deleted['JOURNAL_ENTRY'] = len(je_results)
    print(f"   Deleted: {len(je_results)} receipts (${sum(r[2] for r in je_results if r[2]):.2f})")
    
    # 2. Delete HEFFNER with NULL amount (Duplicates)
    print("\n2. Deleting HEFFNER NULL AMOUNT (Duplicate/import errors)...")
    cur.execute("""
        DELETE FROM receipts
        WHERE vendor_name ILIKE 'HEFFNER%'
        AND gross_amount IS NULL
        RETURNING receipt_id, vendor_name
    """)
    hf_results = cur.fetchall()
    deleted['HEFFNER_NULL'] = len(hf_results)
    print(f"   Deleted: {len(hf_results)} receipts")
    
    # 3. Delete OPENING BALANCE entries
    print("\n3. Deleting OPENING BALANCE entries (Obsolete)...")
    cur.execute("""
        DELETE FROM receipts
        WHERE vendor_name ILIKE 'OPENING BALANCE%'
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    ob_results = cur.fetchall()
    deleted['OPENING_BALANCE'] = len(ob_results)
    print(f"   Deleted: {len(ob_results)} receipts")
    
    # 4. Delete TELUS DUPLICATE IGNORE
    print("\n4. Deleting TELUS [DUPLICATE - IGNORE]...")
    cur.execute("""
        DELETE FROM receipts
        WHERE vendor_name ILIKE '%DUPLICATE%IGNORE%'
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    dup_results = cur.fetchall()
    deleted['TELUS_DUP'] = len(dup_results)
    if dup_results:
        print(f"   Deleted: {len(dup_results)} receipts (${sum(r[2] for r in dup_results if r[2]):.2f})")
    
    conn.commit()
    
    print("\n" + "="*100)
    print("DELETION SUMMARY")
    print("="*100)
    
    total_deleted = sum(deleted.values())
    total_amount = 0
    
    # Get amounts for summary
    for category, count in deleted.items():
        print(f"{category}: {count} receipts deleted")
    
    print(f"\nTOTAL: {total_deleted} receipts deleted")
    
    print("\n" + "="*100)
    print("NEXT STEPS:")
    print("="*100)
    print("""
1. Verify deletion successful with database
2. Run show_remaining_gl_gaps.py to check impact on GL categorization
3. Fix 57 BANK ACCOUNT NUMBER vendors (extract real name from banking)
4. Investigate 2,568 ORPHAN receipts (no banking transaction match)
    """)
    
except Exception as e:
    conn.rollback()
    print(f"ERROR: {e}")
    raise

finally:
    cur.close()
    conn.close()
