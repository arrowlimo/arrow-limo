#!/usr/bin/env python3
"""
Mark obvious import errors and suspicious receipts for deletion.
Criteria:
1. JOURNAL ENTRY (fake entries) - DELETE
2. Bank account numbers as vendor names (000000XXXXXXXX) - REVIEW/DELETE
3. EMAIL TRANSFER without recipient name - REVIEW (need to identify who received)
4. CHEQUE (Payee unknown) - VERIFY against banking before deletion
5. OPENING BALANCE entries - These are likely duplicate/obsolete
6. HEFFNER AUTO FINANCE with NULL amount - Duplicate/import error - DELETE
7. Duplicate insurance entries (same vendor same date) - DELETE extra copy
"""

import psycopg2
import os
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

marked_for_deletion = defaultdict(lambda: {"count": 0, "amount": 0, "reason": ""})
marked_for_review = defaultdict(lambda: {"count": 0, "amount": 0, "reason": ""})

try:
    print("\n" + "="*100)
    print("IDENTIFYING RECEIPTS FOR DELETION/REVIEW")
    print("="*100)
    
    # 1. JOURNAL ENTRY - MARK FOR DELETION (Fake entries)
    print("\n1. MARKING JOURNAL ENTRY FOR DELETION (Fake/Duplicate Entries)")
    cur.execute("""
        UPDATE receipts
        SET marked_for_deletion = true,
            deletion_reason = 'JOURNAL ENTRY - Fake/duplicate entry',
            auto_categorized = true
        WHERE vendor_name ILIKE 'JOURNAL ENTRY%'
        AND marked_for_deletion = false
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    
    je_results = cur.fetchall()
    for receipt_id, vendor_name, amount in je_results:
        marked_for_deletion['JOURNAL ENTRY']['count'] += 1
        if amount:
            marked_for_deletion['JOURNAL ENTRY']['amount'] += amount
    print(f"   Marked {len(je_results)} receipts: ${sum(r[2] for r in je_results if r[2]):.2f}")
    
    # 2. Bank account numbers as vendors - MARK FOR REVIEW
    print("\n2. MARKING BANK ACCOUNT NUMBERS AS VENDOR - MARK FOR REVIEW")
    cur.execute("""
        UPDATE receipts
        SET marked_for_deletion = NULL,
            deletion_reason = 'REVIEW: Bank account/POS number used as vendor name',
            auto_categorized = true
        WHERE vendor_name LIKE '000000%'
        AND marked_for_deletion = false
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    
    ba_results = cur.fetchall()
    for receipt_id, vendor_name, amount in ba_results:
        marked_for_review['BANK_ACCOUNT_VENDOR']['count'] += 1
        if amount:
            marked_for_review['BANK_ACCOUNT_VENDOR']['amount'] += amount
    print(f"   Marked {len(ba_results)} receipts for review: ${sum(r[2] for r in ba_results if r[2]):.2f}")
    
    # 3. HEFFNER AUTO FINANCE with NULL gross_amount - MARK FOR DELETION (Duplicates/Errors)
    print("\n3. MARKING HEFFNER AUTO FINANCE (NULL Amount) FOR DELETION (Duplicates/Errors)")
    cur.execute("""
        UPDATE receipts
        SET marked_for_deletion = true,
            deletion_reason = 'HEFFNER: NULL amount - duplicate/import error',
            auto_categorized = true
        WHERE vendor_name ILIKE 'HEFFNER%'
        AND gross_amount IS NULL
        AND marked_for_deletion = false
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    
    hf_null_results = cur.fetchall()
    for receipt_id, vendor_name, amount in hf_null_results:
        marked_for_deletion['HEFFNER_NULL']['count'] += 1
    print(f"   Marked {len(hf_null_results)} receipts for deletion")
    
    # 4. OPENING BALANCE - MARK FOR DELETION (Should be manual entries only)
    print("\n4. MARKING OPENING BALANCE ENTRIES FOR DELETION (Use manual entries only)")
    cur.execute("""
        UPDATE receipts
        SET marked_for_deletion = true,
            deletion_reason = 'OPENING BALANCE - use manual entries instead',
            auto_categorized = true
        WHERE vendor_name ILIKE 'OPENING BALANCE%'
        AND marked_for_deletion = false
        RETURNING receipt_id, vendor_name, gross_amount
    """)
    
    ob_results = cur.fetchall()
    for receipt_id, vendor_name, amount in ob_results:
        marked_for_deletion['OPENING_BALANCE']['count'] += 1
        if amount:
            marked_for_deletion['OPENING_BALANCE']['amount'] += amount
    print(f"   Marked {len(ob_results)} receipts for deletion")
    
    # 5. Duplicate insurance entries - Find duplicates and mark
    print("\n5. CHECKING FOR DUPLICATE INSURANCE ENTRIES")
    cur.execute("""
        SELECT vendor_name, receipt_date, COUNT(*) as count, 
               SUM(gross_amount) as total,
               ARRAY_AGG(receipt_id) as receipt_ids,
               ARRAY_AGG(banking_transaction_id) as banking_txn_ids
        FROM receipts
        WHERE vendor_name ILIKE '%INSURANCE%'
        AND gl_account_code IN ('5150', '6400')
        GROUP BY vendor_name, receipt_date
        HAVING COUNT(*) > 1
    """)
    
    dup_insurance_results = cur.fetchall()
    insurance_dups = 0
    for vendor_name, receipt_date, count, total, receipt_ids, banking_txn_ids in dup_insurance_results:
        # Mark extras for review (keep one with banking_transaction_id)
        has_banking = [bt_id for bt_id in banking_txn_ids if bt_id is not None]
        if len(has_banking) > 0:
            # Keep the one with banking, mark others for review
            for i, receipt_id in enumerate(receipt_ids):
                if banking_txn_ids[i] is None:
                    cur.execute("""
                        UPDATE receipts
                        SET marked_for_deletion = NULL,
                            deletion_reason = 'DUPLICATE INSURANCE: Keep entry with banking link',
                            auto_categorized = true
                        WHERE receipt_id = %s
                        AND marked_for_deletion = false
                    """, (receipt_id,))
                    insurance_dups += 1
    
    print(f"   Marked {insurance_dups} duplicate insurance entries for review")
    
    # 6. ETRANSFER variants - Consolidate ETRANSFER FEE entries
    print("\n6. CONSOLIDATING ETRANSFER FEE ENTRIES")
    cur.execute("""
        UPDATE receipts
        SET vendor_name = 'ETRANSFER FEE',
            auto_categorized = true
        WHERE vendor_name ILIKE 'EMAIL TRANSFER FEE%'
        AND vendor_name != 'ETRANSFER FEE'
        RETURNING COUNT(*) as count
    """)
    print(f"   Consolidated E-TRANSFER FEE variants")
    
    conn.commit()
    
    print("\n" + "="*100)
    print("SUMMARY OF MARKED RECEIPTS")
    print("="*100)
    
    print("\n[MARKED FOR DELETION]")
    total_delete_count = 0
    total_delete_amount = 0
    for category in sorted(marked_for_deletion.keys()):
        data = marked_for_deletion[category]
        if data['count'] > 0:
            print(f"  {category}: {data['count']:,} receipts (${data['amount']:,.2f})")
            total_delete_count += data['count']
            total_delete_amount += data['amount']
    
    print(f"\nTOTAL MARKED FOR DELETION: {total_delete_count:,} receipts (${total_delete_amount:,.2f})")
    
    print("\n[MARKED FOR REVIEW]")
    total_review_count = 0
    total_review_amount = 0
    for category in sorted(marked_for_review.keys()):
        data = marked_for_review[category]
        if data['count'] > 0:
            print(f"  {category}: {data['count']:,} receipts (${data['amount']:,.2f})")
            total_review_count += data['count']
            total_review_amount += data['amount']
    
    print(f"\nTOTAL MARKED FOR REVIEW: {total_review_count:,} receipts (${total_review_amount:,.2f})")
    
    print("\n" + "="*100)
    print("NEXT STEP: Review marked receipts, then run deletion script")
    print("="*100)
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    raise

finally:
    cur.close()
    conn.close()
