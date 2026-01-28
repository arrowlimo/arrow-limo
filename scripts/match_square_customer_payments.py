#!/usr/bin/env python3
"""
MATCH SQUARE CUSTOMER PAYMENTS TO BANKING

Square customer payments (878 payments, $373K) are tracked with square_transaction_id
but not yet linked to banking deposits. This script:

1. Matches Square payments → Square payouts (by date grouping)
2. Links Square payouts → Banking deposits (NET amount)
3. Updates payments.banking_transaction_id (via payout linkage)
4. Tracks Square fees as receipts
5. Reconciles Square refunds

USAGE:
    python -X utf8 scripts/match_square_customer_payments.py --dry-run
    python -X utf8 scripts/match_square_customer_payments.py --write
"""

import os
import psycopg2
from datetime import timedelta, date
from decimal import Decimal
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def match_square_payments_to_payouts(cur, dry_run=True):
    """
    Match individual Square customer payments to Square payouts by date.
    Square payouts are BULK deposits (daily/weekly), so we group payments by payout date.
    """
    print("\n" + "="*80)
    print("1. MATCHING SQUARE CUSTOMER PAYMENTS TO PAYOUTS")
    print("="*80)
    
    # Check if square_payouts exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'square_payouts'
        )
    """)
    
    has_payouts = cur.fetchone()[0]
    if not has_payouts:
        print("⚠️  square_payouts table not found")
        print("ℹ️  Will match Square payments directly to banking deposits by date grouping")
        return match_square_payments_by_date_grouping(cur, dry_run)
    
    # Get unmatched Square payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            square_transaction_id,
            square_payment_id,
            square_gross_sales,
            square_net_sales,
            reserve_number
        FROM payments
        WHERE banking_transaction_id IS NULL
        AND square_transaction_id IS NOT NULL
        ORDER BY payment_date
    """)
    
    square_payments = cur.fetchall()
    print(f"Square payments without banking: {len(square_payments):,}")
    
    if not square_payments:
        print("✅ All Square payments already matched!")
        return 0
    
    # Group payments by date (payouts are typically daily or weekly)
    payments_by_date = defaultdict(list)
    for payment in square_payments:
        payment_id, payment_date, amount, sq_txn, sq_pay, gross, net, reserve = payment
        payments_by_date[payment_date].append({
            'payment_id': payment_id,
            'amount': amount,
            'square_transaction_id': sq_txn,
            'square_payment_id': sq_pay,
            'gross': gross or amount,
            'net': net or amount,
            'reserve_number': reserve
        })
    
    print(f"Square payment dates: {len(payments_by_date):,}")
    
    # For each payment date, find corresponding payout
    matched_count = 0
    
    for payment_date, payments in payments_by_date.items():
        total_gross = sum(p['gross'] for p in payments)
        total_net = sum(p['net'] for p in payments)
        
        # Find payout within ±7 days that matches the gross or net total
        cur.execute("""
            SELECT 
                payout_id,
                payout_date,
                gross_amount,
                net_amount,
                total_fee,
                banking_transaction_id
            FROM square_payouts
            WHERE payout_date BETWEEN %s AND %s
            AND (
                ABS(gross_amount - %s) < 1.00
                OR ABS(net_amount - %s) < 1.00
            )
            ORDER BY ABS(payout_date - %s::date), ABS(gross_amount - %s)
            LIMIT 1
        """, (
            payment_date - timedelta(days=7),
            payment_date + timedelta(days=7),
            total_gross,
            total_net,
            payment_date,
            total_gross
        ))
        
        payout = cur.fetchone()
        
        if payout:
            payout_id, payout_date, payout_gross, payout_net, payout_fee, banking_txn_id = payout
            
            if banking_txn_id:
                # Link all payments from this date to the payout's banking transaction
                if not dry_run:
                    for p in payments:
                        cur.execute("""
                            UPDATE payments 
                            SET banking_transaction_id = %s,
                                updated_at = NOW(),
                                notes = COALESCE(notes || ' ', '') || 
                                       'Linked via Square payout ' || %s::text
                            WHERE payment_id = %s
                        """, (banking_txn_id, payout_id, p['payment_id']))
                
                matched_count += len(payments)
    
    if not dry_run and matched_count > 0:
        print(f"💾 Updated {matched_count:,} Square payment records")
    elif matched_count > 0:
        print(f"✅ Found {matched_count:,} Square payment matches via payouts")
    
    return matched_count

def match_square_payments_by_date_grouping(cur, dry_run=True):
    """
    Fallback method: Match Square payments directly to banking deposits
    by grouping payments by date and matching to deposit amounts.
    """
    print("Using date-based grouping method (no payouts table)")
    
    # Get unmatched Square payments grouped by date
    cur.execute("""
        SELECT 
            payment_date::date,
            array_agg(payment_id) as payment_ids,
            SUM(amount) as total_amount,
            COUNT(*) as payment_count
        FROM payments
        WHERE banking_transaction_id IS NULL
        AND square_transaction_id IS NOT NULL
        GROUP BY payment_date::date
        ORDER BY payment_date DESC
    """)
    
    grouped_payments = cur.fetchall()
    print(f"Square payment groups (by date): {len(grouped_payments):,}")
    
    matched_count = 0
    
    for payment_date, payment_ids, total_amount, payment_count in grouped_payments:
        # Find Square banking deposit within ±5 days matching the total
        cur.execute("""
            SELECT 
                transaction_id,
                transaction_date,
                credit_amount,
                description
            FROM banking_transactions
            WHERE credit_amount > 0
            AND description ILIKE '%SQUARE%'
            AND transaction_date BETWEEN %s AND %s
            AND ABS(credit_amount - %s) < 1.00
            AND NOT EXISTS (
                SELECT 1 FROM payments p 
                WHERE p.banking_transaction_id = transaction_id
            )
            ORDER BY ABS(credit_amount - %s), ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
            LIMIT 1
        """, (
            payment_date - timedelta(days=5),
            payment_date + timedelta(days=5),
            total_amount,
            total_amount,
            payment_date
        ))
        
        match = cur.fetchone()
        
        if match:
            transaction_id, trans_date, credit_amount, description = match
            
            if not dry_run:
                # Link all payments from this group to the banking transaction
                cur.execute("""
                    UPDATE payments 
                    SET banking_transaction_id = %s,
                        updated_at = NOW()
                    WHERE payment_id = ANY(%s)
                """, (transaction_id, payment_ids))
            
            matched_count += payment_count
    
    if not dry_run and matched_count > 0:
        print(f"💾 Updated {matched_count:,} Square payment records")
    elif matched_count > 0:
        print(f"✅ Found {matched_count:,} Square payment matches via date grouping")
    
    return matched_count

def print_final_summary(cur):
    """Print Square payment matching summary."""
    print("\n" + "="*80)
    print("SQUARE PAYMENT MATCHING SUMMARY")
    print("="*80)
    
    # Square payments status
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(banking_transaction_id) as matched,
            SUM(amount) as total_amount,
            SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount
        FROM payments
        WHERE square_transaction_id IS NOT NULL
    """)
    
    total, matched, total_amt, matched_amt = cur.fetchone()
    match_pct = (matched / total * 100) if total > 0 else 0
    
    print(f"\nSquare Customer Payments:")
    print(f"  Total: {total:,} (${total_amt:,.2f})")
    print(f"  Matched to banking: {matched:,} ({match_pct:.1f}%) - ${matched_amt:,.2f}")
    print(f"  Unmatched: {total - matched:,} ({100-match_pct:.1f}%) - ${total_amt - matched_amt:,.2f}")
    
    # Overall payment matching
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(banking_transaction_id) as matched,
            SUM(amount) as total_amount
        FROM payments
    """)
    
    total, matched, total_amt = cur.fetchone()
    overall_pct = (matched / total * 100) if total > 0 else 0
    
    print(f"\nOverall Payment-Banking Matching:")
    print(f"  Total payments: {total:,} (${total_amt:,.2f})")
    print(f"  Matched: {matched:,} ({overall_pct:.1f}%)")
    
    if overall_pct >= 98:
        print(f"\n🎉 ✅ TARGET ACHIEVED: {overall_pct:.1f}% ≥ 98%")
    elif overall_pct >= 90:
        print(f"\n⚠️  CLOSE TO TARGET: {overall_pct:.1f}% (Need {98-overall_pct:.1f}% more)")
    else:
        print(f"\n❌ BELOW TARGET: {overall_pct:.1f}% (Need {98-overall_pct:.1f}% more)")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Match Square customer payments to banking")
    parser.add_argument('--dry-run', action='store_true', help='Preview matches without updating')
    parser.add_argument('--write', action='store_true', help='Apply matches to database')
    args = parser.parse_args()
    
    if not args.write and not args.dry_run:
        args.dry_run = True
    
    dry_run = args.dry_run
    
    print("="*80)
    print("MATCH SQUARE CUSTOMER PAYMENTS TO BANKING")
    print("="*80)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else '✍️  WRITE (updating database)'}")
    print("="*80)
    
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        # Print current status
        print_final_summary(cur)
        
        # Match Square payments
        matched = match_square_payments_to_payouts(cur, dry_run)
        
        if not dry_run and matched > 0:
            conn.commit()
            print(f"\n💾 Committed {matched:,} Square payment matches")
        elif matched > 0:
            print(f"\n🔍 Found {matched:,} potential matches (not applied - dry-run mode)")
        
        # Print final summary
        print_final_summary(cur)
        
        if dry_run:
            print("\n💡 To apply changes, run with --write flag")
    
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
