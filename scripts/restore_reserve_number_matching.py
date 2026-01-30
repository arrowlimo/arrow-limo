#!/usr/bin/env python3
"""
RESTORE PAYMENT-BANKING MATCHING VIA RESERVE_NUMBER

reserve_number is the LMS business key (6-digit number) that links:
  - payments.reserve_number → charters.reserve_number
  - charters.reserve_number → banking deposits (customer payments)

This script restores the 98% payment-banking matching by:
1. Finding banking deposits that match charter amounts (customer payments)
2. Linking all payments with that reserve_number to the banking transaction

USAGE:
    python -X utf8 scripts/restore_reserve_number_matching.py --dry-run
    python -X utf8 scripts/restore_reserve_number_matching.py --write
"""

import os
import psycopg2
from datetime import timedelta

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def match_payments_via_reserve_number(cur, dry_run=True):
    """
    Match payments to banking by finding charter deposits via reserve_number.
    
    Logic:
    1. Find charters with reserve_number
    2. Find banking deposits that match charter amount + date
    3. Link ALL payments for that reserve_number to the banking transaction
    """
    print("\n" + "="*80)
    print("MATCHING PAYMENTS TO BANKING VIA RESERVE_NUMBER")
    print("="*80)
    
    # Step 1: Find charter → banking deposit matches
    print("\n1. Finding charter-banking deposit matches...")
    
    cur.execute("""
        WITH charter_banking_matches AS (
            SELECT DISTINCT ON (c.reserve_number)
                c.reserve_number,
                c.charter_id,
                c.charter_date,
                c.total_amount_due,
                b.transaction_id as banking_transaction_id,
                b.transaction_date,
                b.credit_amount,
                ABS(c.total_amount_due - b.credit_amount) as amount_diff,
                ABS(EXTRACT(EPOCH FROM (c.charter_date::timestamp - b.transaction_date::timestamp))) / 86400.0 as days_diff
            FROM charters c
            INNER JOIN banking_transactions b ON 
                b.credit_amount > 0
                AND b.transaction_date BETWEEN c.charter_date - INTERVAL '10 days' AND c.charter_date + INTERVAL '30 days'
                AND ABS(c.total_amount_due - b.credit_amount) < 5.00
            WHERE c.reserve_number IS NOT NULL
            ORDER BY c.reserve_number, amount_diff ASC, days_diff ASC
        )
        SELECT 
            COUNT(*) as charter_matches,
            SUM(total_amount_due) as total_charter_amount
        FROM charter_banking_matches
    """)
    
    charter_matches, charter_amount = cur.fetchone()
    print(f"   Found {charter_matches:,} charters with banking deposit matches (${charter_amount:,.2f})")
    
    # Step 2: Count how many payments can be matched
    print("\n2. Counting matchable payments...")
    
    cur.execute("""
        WITH charter_banking_matches AS (
            SELECT DISTINCT ON (c.reserve_number)
                c.reserve_number,
                b.transaction_id as banking_transaction_id
            FROM charters c
            INNER JOIN banking_transactions b ON 
                b.credit_amount > 0
                AND b.transaction_date BETWEEN c.charter_date - INTERVAL '10 days' AND c.charter_date + INTERVAL '30 days'
                AND ABS(c.total_amount_due - b.credit_amount) < 5.00
            WHERE c.reserve_number IS NOT NULL
            ORDER BY c.reserve_number, ABS(c.total_amount_due - b.credit_amount) ASC
        )
        SELECT 
            COUNT(DISTINCT p.payment_id) as matchable_payments,
            SUM(p.amount) as matchable_amount,
            COUNT(DISTINCT p.reserve_number) as unique_reserves
        FROM payments p
        INNER JOIN charter_banking_matches cbm ON cbm.reserve_number = p.reserve_number
        WHERE p.banking_transaction_id IS NULL
    """)
    
    matchable_payments, matchable_amount, unique_reserves = cur.fetchone()
    
    if not matchable_payments:
        print("   ❌ No payments can be matched via reserve_number")
        return 0
    
    print(f"   ✅ Can match {matchable_payments:,} payments via {unique_reserves:,} reserve numbers")
    print(f"      Total amount: ${matchable_amount:,.2f}")
    
    # Step 3: Apply matches
    if not dry_run:
        print("\n3. Applying matches...")
        
        cur.execute("""
            WITH charter_banking_matches AS (
                SELECT DISTINCT ON (c.reserve_number)
                    c.reserve_number,
                    b.transaction_id as banking_transaction_id
                FROM charters c
                INNER JOIN banking_transactions b ON 
                    b.credit_amount > 0
                    AND b.transaction_date BETWEEN c.charter_date - INTERVAL '10 days' AND c.charter_date + INTERVAL '30 days'
                    AND ABS(c.total_amount_due - b.credit_amount) < 5.00
                WHERE c.reserve_number IS NOT NULL
                ORDER BY c.reserve_number, ABS(c.total_amount_due - b.credit_amount) ASC
            )
            UPDATE payments p
            SET banking_transaction_id = cbm.banking_transaction_id,
                updated_at = NOW()
            FROM charter_banking_matches cbm
            WHERE cbm.reserve_number = p.reserve_number
            AND p.banking_transaction_id IS NULL
        """)
        
        updated_count = cur.rowcount
        print(f"   💾 Updated {updated_count:,} payment records")
        return updated_count
    else:
        print(f"   🔍 Would update {matchable_payments:,} payments (dry-run mode)")
        
        # Show sample matches
        print("\n   📋 Sample matches:")
        cur.execute("""
            WITH charter_banking_matches AS (
                SELECT DISTINCT ON (c.reserve_number)
                    c.reserve_number,
                    c.total_amount_due,
                    b.transaction_id as banking_transaction_id,
                    b.transaction_date,
                    b.credit_amount
                FROM charters c
                INNER JOIN banking_transactions b ON 
                    b.credit_amount > 0
                    AND b.transaction_date BETWEEN c.charter_date - INTERVAL '10 days' AND c.charter_date + INTERVAL '30 days'
                    AND ABS(c.total_amount_due - b.credit_amount) < 5.00
                WHERE c.reserve_number IS NOT NULL
                ORDER BY c.reserve_number, ABS(c.total_amount_due - b.credit_amount) ASC
            )
            SELECT 
                p.payment_id,
                p.reserve_number,
                p.amount,
                p.payment_date,
                cbm.banking_transaction_id,
                cbm.transaction_date,
                cbm.credit_amount
            FROM payments p
            INNER JOIN charter_banking_matches cbm ON cbm.reserve_number = p.reserve_number
            WHERE p.banking_transaction_id IS NULL
            LIMIT 10
        """)
        
        for payment_id, reserve, amount, pay_date, banking_id, bank_date, bank_amount in cur.fetchall():
            print(f"      Payment {payment_id} (Rsv {reserve}, ${amount:.2f}, {pay_date})")
            print(f"         → Banking {banking_id} (${bank_amount:.2f}, {bank_date})")
        
        return matchable_payments

def print_final_summary(cur):
    """Print final payment-banking matching summary."""
    print("\n" + "="*80)
    print("PAYMENT-BANKING MATCHING SUMMARY")
    print("="*80)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(banking_transaction_id) as matched,
            SUM(amount) as total_amount,
            SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount
        FROM payments
    """)
    
    total, matched, total_amt, matched_amt = cur.fetchone()
    match_pct = (matched / total * 100) if total > 0 else 0
    
    print(f"\nTotal payments: {total:,} (${total_amt:,.2f})")
    print(f"Matched to banking: {matched:,} ({match_pct:.1f}%) - ${matched_amt:,.2f}")
    print(f"Unmatched: {total - matched:,} ({100-match_pct:.1f}%) - ${total_amt - matched_amt:,.2f}")
    
    # Show breakdown by payment method
    print("\n📊 Breakdown by payment method:")
    cur.execute("""
        SELECT 
            COALESCE(payment_method, 'NULL') as method,
            COUNT(*) as total,
            COUNT(banking_transaction_id) as matched,
            SUM(amount) as total_amt
        FROM payments
        GROUP BY payment_method
        ORDER BY total DESC
        LIMIT 10
    """)
    
    for method, count, matched_count, amt in cur.fetchall():
        pct = (matched_count / count * 100) if count > 0 else 0
        print(f"  {method:20s}: {matched_count:>6,}/{count:<6,} ({pct:5.1f}%)  ${amt:>12,.2f}")
    
    if match_pct >= 98:
        print(f"\n🎉 ✅ TARGET ACHIEVED: {match_pct:.1f}% ≥ 98%")
    elif match_pct >= 90:
        print(f"\n⚠️  CLOSE TO TARGET: {match_pct:.1f}% (Need {98-match_pct:.1f}% more)")
    else:
        print(f"\n❌ BELOW TARGET: {match_pct:.1f}% (Need {98-match_pct:.1f}% more)")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Restore payment-banking matching via reserve_number")
    parser.add_argument('--dry-run', action='store_true', help='Preview matches without updating')
    parser.add_argument('--write', action='store_true', help='Apply matches to database')
    args = parser.parse_args()
    
    if not args.write and not args.dry_run:
        args.dry_run = True
    
    dry_run = args.dry_run
    
    print("="*80)
    print("RESTORE PAYMENT-BANKING MATCHING VIA RESERVE_NUMBER")
    print("="*80)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else '✍️  WRITE (updating database)'}")
    print("="*80)
    
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        # Show current status
        print_final_summary(cur)
        
        # Run matching
        matched = match_payments_via_reserve_number(cur, dry_run)
        
        if not dry_run and matched > 0:
            conn.commit()
            print(f"\n💾 Committed {matched:,} payment matches")
        elif matched > 0:
            print(f"\n🔍 Found {matched:,} potential matches (not applied - dry-run mode)")
        
        # Show final summary
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
