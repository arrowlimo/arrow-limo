#!/usr/bin/env python3
"""
Square Duplicate Analysis & Cleanup Preparation

Shows:
1. All 31 identified duplicates with details
2. Which payments to DELETE (19 with 0.95 confidence)
3. Which need MANUAL REVIEW (12 with 0.75 confidence)
4. Multi-charter payment verification
5. Dollar amount recovery
"""

import psycopg2
import pandas as pd
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("SQUARE DUPLICATE ANALYSIS & CLEANUP PREPARATION")
    print("="*100)
    
    # Get exact duplicates (0.95 confidence)
    cur.execute("""
        SELECT 
            s.primary_payment_id,
            s.duplicate_payment_id,
            s.amount,
            s.payment_date,
            s.confidence_score,
            s.reason,
            p1.notes as primary_notes,
            p2.notes as duplicate_notes
        FROM square_duplicates_staging s
        JOIN payments p1 ON s.primary_payment_id = p1.payment_id
        JOIN payments p2 ON s.duplicate_payment_id = p2.payment_id
        WHERE s.confidence_score = 0.95
        ORDER BY s.amount DESC, s.payment_date
    """)
    
    exact_dupes = cur.fetchall()
    
    print(f"\n{'='*100}")
    print(f"EXACT DUPLICATES (Confidence 0.95) - SAFE TO DELETE")
    print(f"{'='*100}")
    print(f"\nFound {len(exact_dupes)} exact duplicate pairs (same amount + same date)")
    print(f"Action: DELETE the duplicate_payment_id, keep primary_payment_id\n")
    
    delete_ids = []
    recovery_amount = 0
    
    for primary, duplicate, amount, date, conf, reason, notes1, notes2 in exact_dupes:
        delete_ids.append(duplicate)
        recovery_amount += amount
        print(f"  PRIMARY: {primary:6d} | DUPLICATE: {duplicate:6d} | Amount: ${amount:10.2f} | Date: {date}")
        print(f"           Confidence: {conf} | Keep {primary}, DELETE {duplicate}")
    
    print(f"\n  TOTAL RECOVERY: ${recovery_amount:,.2f} ({len(exact_dupes)} duplicate entries)")
    
    # Get near-duplicates (0.75 confidence)
    cur.execute("""
        SELECT 
            s.primary_payment_id,
            s.duplicate_payment_id,
            s.amount,
            s.payment_date,
            s.duplicate_date_diff,
            s.confidence_score,
            p1.reserve_number as primary_reserve,
            p2.reserve_number as duplicate_reserve,
            p1.notes as primary_notes,
            p2.notes as duplicate_notes
        FROM square_duplicates_staging s
        JOIN payments p1 ON s.primary_payment_id = p1.payment_id
        JOIN payments p2 ON s.duplicate_payment_id = p2.payment_id
        WHERE s.confidence_score = 0.75
        ORDER BY s.amount DESC, s.payment_date
    """)
    
    near_dupes = cur.fetchall()
    
    print(f"\n{'='*100}")
    print(f"NEAR-DUPLICATES (Confidence 0.75) - MANUAL REVIEW REQUIRED")
    print(f"{'='*100}")
    print(f"\nFound {len(near_dupes)} near-duplicate pairs (same amount within 1 day)")
    print(f"CAUTION: May be legitimate multi-charter payments!\n")
    
    for primary, duplicate, amount, date, date_diff, conf, pres, dres, notes1, notes2 in near_dupes:
        linked_status = "✅ LINKED" if pres else "❌ ORPHAN"
        print(f"  PRIMARY: {primary:6d} ({linked_status:12s}) | DUPLICATE: {duplicate:6d}")
        print(f"           Amount: ${amount:10.2f} | Date: {date} (diff: {date_diff} days)")
        print(f"           Notes P: {str(notes1)[:50] if notes1 else 'None'}")
        print(f"           Notes D: {str(notes2)[:50] if notes2 else 'None'}")
        print()
    
    # Check for multi-charter indicators
    print(f"{'='*100}")
    print(f"MULTI-CHARTER PAYMENT CHECK")
    print(f"{'='*100}")
    print(f"\nVerifying if duplicates are legitimate multi-charter payments...\n")
    
    cur.execute("""
        SELECT 
            s.primary_payment_id,
            s.duplicate_payment_id,
            s.amount,
            s.payment_date,
            (SELECT COUNT(*) FROM charters c 
             WHERE c.charter_date::DATE = s.payment_date) as charters_that_day,
            (SELECT COUNT(DISTINCT square_customer_email) FROM payments p
             WHERE p.payment_id IN (s.primary_payment_id, s.duplicate_payment_id)
             AND p.square_customer_email IS NOT NULL) as unique_emails
        FROM square_duplicates_staging s
        WHERE s.confidence_score = 0.75
        ORDER BY s.amount DESC
    """)
    
    multi_charter_checks = cur.fetchall()
    
    for primary, duplicate, amount, date, charters_count, unique_emails in multi_charter_checks:
        is_multi = charters_count > 1 or unique_emails > 1
        indicator = "⚠️ LIKELY MULTI-CHARTER" if is_multi else "🔴 LIKELY DUPLICATE"
        print(f"  {indicator} | Payments {primary}/{duplicate}")
        print(f"     Amount: ${amount:10.2f} | Charters on {date}: {charters_count} | Unique emails: {unique_emails}")
    
    # Summary
    print(f"\n{'='*100}")
    print(f"CLEANUP SUMMARY")
    print(f"{'='*100}")
    
    print(f"\n✅ SAFE TO DELETE (19 exact duplicates):")
    print(f"   IDs: {sorted(delete_ids)}")
    print(f"   Recovery: ${recovery_amount:,.2f}")
    
    print(f"\n⚠️ REQUIRES MANUAL VERIFICATION (12 near-duplicates):")
    print(f"   Check if multi-charter payments before deletion")
    print(f"   Expected recovery if all deleted: ${sum([amt for _, _, amt, _, _, _, _, _, _, _ in near_dupes]):,.2f}")
    
    print(f"\n📊 FINAL IMPACT:")
    print(f"   Total duplicates to handle: {len(exact_dupes) + len(near_dupes)} payments")
    print(f"   Total amount to recover: ${recovery_amount + sum([amt for _, _, amt, _, _, _, _, _, _, _ in near_dupes]):,.2f}")
    print(f"   New orphaned count after cleanup: {217 - len(exact_dupes)} (if no near-dupes deleted)")
    print(f"   New orphaned count if all deleted: {217 - len(exact_dupes) - len(near_dupes)}")
    
    # Generate DELETE statement
    print(f"\n{'='*100}")
    print(f"CLEANUP EXECUTION")
    print(f"{'='*100}")
    
    if delete_ids:
        delete_str = ', '.join(str(id) for id in delete_ids)
        print(f"\n✅ READY-TO-EXECUTE DELETE STATEMENT (19 safe deletions):\n")
        print(f"DELETE FROM payments WHERE payment_id IN ({delete_str});")
        print(f"\nExpected rows deleted: {len(delete_ids)}")
        print(f"Expected amount recovered: ${recovery_amount:,.2f}")
    
    print(f"\n📋 For near-duplicates, manually review each before deletion.")
    print(f"   SQL to view: SELECT * FROM square_duplicates_staging WHERE confidence_score = 0.75;")
    
    cur.close()
    conn.close()
    
    print(f"\n{'='*100}\n")

if __name__ == '__main__':
    main()
