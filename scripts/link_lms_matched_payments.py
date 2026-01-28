#!/usr/bin/env python3
"""
TRACK A: Link 68 LMS-matched orphaned payments to their charters

These 68 payments were found in LMS with matching amounts and dates (±3 days).
This script safely links them to their reserve_numbers from LMS.

Strategy: Use LMS reserve data to populate reserve_number field
"""

import os
import psycopg2
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("l:/limo/.env")
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "almsdata")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def link_lms_matched_payments(dry_run=True):
    """Link payments that have LMS matches"""
    
    # Read LMS export
    lms_df = pd.read_csv("reports/lms_payment_reserve_export.csv")
    lms_df['lms_datetime'] = pd.to_datetime(lms_df['date'])
    
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cur = conn.cursor()
    
    # Get orphaned payments
    cur.execute("""
    SELECT p.payment_id, p.amount, DATE(p.payment_date) as payment_date
    FROM payments p
    WHERE p.reserve_number IS NULL
      AND p.payment_date >= '2025-09-10'
      AND p.payment_method = 'credit_card'
    ORDER BY p.payment_date, p.amount;
    """)
    
    orphans = cur.fetchall()
    print(f"\n📊 Processing {len(orphans)} orphaned payments...\n")
    
    linked = []
    skipped_nomatch = []
    skipped_ambiguous = []
    
    for payment_id, amount, payment_date in orphans:
        # Find LMS matches: amount + date within ±3 days
        payment_ts = pd.Timestamp(payment_date)
        lms_match = lms_df[
            (lms_df['amount'] == amount) &
            ((lms_df['lms_datetime'] - payment_ts).dt.days.abs() <= 3)
        ]
        
        if len(lms_match) == 0:
            # No match in LMS
            skipped_nomatch.append({
                'payment_id': payment_id,
                'amount': float(amount),
                'payment_date': payment_date,
                'reason': 'Not in LMS'
            })
        elif len(lms_match) == 1:
            # Perfect match: 1 payment in LMS
            lms_reserve = lms_match.iloc[0]['reserve']
            linked.append({
                'payment_id': payment_id,
                'amount': float(amount),
                'payment_date': payment_date,
                'reserve_number': str(lms_reserve)
            })
            
            # Update database
            if not dry_run:
                cur.execute("""
                UPDATE payments
                SET reserve_number = %s,
                    notes = CONCAT(notes, ' | LINKED from LMS')
                WHERE payment_id = %s
                  AND reserve_number IS NULL;
                """, (str(lms_reserve), payment_id))
        else:
            # Ambiguous: multiple LMS matches
            reserves = lms_match['reserve'].unique().tolist()
            skipped_ambiguous.append({
                'payment_id': payment_id,
                'amount': float(amount),
                'payment_date': payment_date,
                'lms_reserves': [str(r) for r in reserves],
                'reason': f'Multiple LMS matches: {len(lms_match)} records'
            })
    
    # Commit if not dry run
    if not dry_run:
        conn.commit()
        print(f"✅ **COMMITTED {len(linked)} payment linkages to database**\n")
    else:
        print(f"⚠️  **DRY RUN - No changes written**\n")
    
    # Report
    print("=" * 80)
    print("TRACK A: LMS-MATCHED PAYMENT LINKING RESULTS")
    print("=" * 80)
    print(f"\n✅ Successfully linked:        {len(linked):3} / {len(orphans)} ({100*len(linked)/len(orphans):5.1f}%)")
    print(f"❌ No LMS match:              {len(skipped_nomatch):3} / {len(orphans)} ({100*len(skipped_nomatch)/len(orphans):5.1f}%)")
    print(f"⚠️  Ambiguous (multiple LMS): {len(skipped_ambiguous):3} / {len(orphans)} ({100*len(skipped_ambiguous)/len(orphans):5.1f}%)")
    print(f"\n{'TOTAL':.<40} {len(orphans):>3}")
    
    # Sample of linked
    if linked:
        print(f"\n📋 SAMPLE OF LINKED PAYMENTS (first 10):\n")
        print(f"{'PaymentID':<10} {'Amount':<12} {'Date':<12} {'Reserve #':<12}")
        print(f"{'-'*10} {'-'*12} {'-'*12} {'-'*12}")
        for m in linked[:10]:
            print(f"{m['payment_id']:<10} ${m['amount']:<11,.2f} {str(m['payment_date']):<12} {m['reserve_number']:<12}")
        if len(linked) > 10:
            print(f"\n... and {len(linked)-10} more payments\n")
    
    # Summary for unmatched
    if skipped_nomatch:
        print(f"\n🔴 UNMATCHED IN LMS ({len(skipped_nomatch)} payments):")
        print(f"   These will be investigated in TRACK B\n")
    
    cur.close()
    conn.close()
    
    return len(linked), len(skipped_nomatch), len(skipped_ambiguous)


if __name__ == "__main__":
    import sys
    
    apply_mode = "--apply" in sys.argv or "-a" in sys.argv
    
    if not apply_mode:
        print("\n⚠️  Running in DRY RUN mode (no changes will be written)")
        print("    To apply: python link_lms_matched_payments.py --apply\n")
    
    linked, nomatch, ambiguous = link_lms_matched_payments(dry_run=not apply_mode)
    
    print("=" * 80)
    if not apply_mode and linked > 0:
        print(f"\n✅ Dry-run successful! Ready to link {linked} payments.")
        print(f"   Command: python -X utf8 scripts/link_lms_matched_payments.py --apply\n")
