#!/usr/bin/env python3
"""
COMPREHENSIVE PAYMENT-BANKING MATCHING FROM LMS

This syncs LMS payment data and matches ALL payment types to banking:
1. Load charter-payment links from LMS (source of truth)
2. Match payment_method patterns to banking transactions:
   - bank_transfer → E-Transfer deposits, Square deposits, Wire transfers
   - cash → Cash deposits, Branch deposits
   - check → Check deposits (by check number)
   - credit_card → Global Payments, merchant deposits
   - unknown → Best guess matching by date+amount

Target: 98%+ payment-banking matching

USAGE:
    python -X utf8 scripts/comprehensive_payment_banking_match.py --dry-run
    python -X utf8 scripts/comprehensive_payment_banking_match.py --write
"""

import os
import psycopg2
import pyodbc
from datetime import timedelta
from decimal import Decimal

def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def get_lms_conn():
    lms_path = r"L:\limo\lms.mdb"
    return pyodbc.connect(f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};')

def match_by_charter_reserve(cur, dry_run=True):
    """
    Match payments to banking via charter reserve_number.
    If charter has a banking deposit, link payment to same banking transaction.
    """
    print("\n" + "="*80)
    print("1. MATCHING PAYMENTS VIA CHARTER RESERVE NUMBER")
    print("="*80)
    
    # Find payments linked to charters that have banking deposits
    cur.execute("""
        WITH charter_banking AS (
            SELECT DISTINCT
                c.reserve_number,
                r.banking_transaction_id
            FROM charters c
            INNER JOIN receipts r ON r.banking_transaction_id IS NOT NULL
            INNER JOIN banking_transactions b ON b.transaction_id = r.banking_transaction_id
            WHERE c.reserve_number IS NOT NULL
            AND b.credit_amount > 0
            AND ABS(c.total_amount_due - b.credit_amount) < 10.00
            AND ABS(EXTRACT(EPOCH FROM (c.charter_date - b.transaction_date))) < 7*86400
        )
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.amount,
            cb.banking_transaction_id
        FROM payments p
        INNER JOIN charter_banking cb ON cb.reserve_number = p.reserve_number
        WHERE p.banking_transaction_id IS NULL
        AND p.reserve_number IS NOT NULL
    """)
    
    matches = cur.fetchall()
    print(f"✅ Found {len(matches):,} payments matchable via charter reserve")
    
    if matches and not dry_run:
        for payment_id, reserve, amount, banking_txn_id in matches:
            cur.execute("""
                UPDATE payments 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (banking_txn_id, payment_id))
        print(f"💾 Updated {len(matches):,} payments")
    
    return len(matches)

def match_remaining_by_method_and_date(cur, dry_run=True):
    """
    Match remaining payments by payment_method + date + amount.
    This is the comprehensive matching for all payment types.
    """
    print("\n" + "="*80)
    print("2. MATCHING REMAINING PAYMENTS BY METHOD + DATE + AMOUNT")
    print("="*80)
    
    # Get all unmatched payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            check_number,
            reserve_number
        FROM payments
        WHERE banking_transaction_id IS NULL
        ORDER BY payment_date DESC, amount DESC
    """)
    
    unmatched = cur.fetchall()
    print(f"Unmatched payments: {len(unmatched):,}")
    
    matched_count = 0
    
    for payment_id, payment_date, amount, payment_method, check_number, reserve in unmatched:
        banking_txn_id = None
        
        # Strategy depends on payment method
        if payment_method in ('bank_transfer', 'e-transfer'):
            # Match to E-Transfer or deposit credits within ±3 days
            cur.execute("""
                SELECT transaction_id
                FROM banking_transactions
                WHERE credit_amount > 0
                AND transaction_date BETWEEN %s AND %s
                AND ABS(credit_amount - %s) < 0.01
                AND (
                    description ILIKE '%%E-TRANSFER%%'
                    OR description ILIKE '%%EMAIL%%TRANSFER%%'
                    OR description ILIKE '%%DEPOSIT%%'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM payments p 
                    WHERE p.banking_transaction_id = transaction_id
                )
                ORDER BY ABS(credit_amount - %s), ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
                LIMIT 1
            """, (payment_date - timedelta(days=3), payment_date + timedelta(days=3), amount, amount, payment_date))
            
        elif payment_method == 'cash':
            # Match to cash deposits
            cur.execute("""
                SELECT transaction_id
                FROM banking_transactions
                WHERE credit_amount > 0
                AND transaction_date BETWEEN %s AND %s
                AND ABS(credit_amount - %s) < 0.01
                AND description ILIKE '%%CASH%%DEPOSIT%%'
                AND NOT EXISTS (
                    SELECT 1 FROM payments p 
                    WHERE p.banking_transaction_id = transaction_id
                )
                ORDER BY ABS(credit_amount - %s), ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
                LIMIT 1
            """, (payment_date - timedelta(days=3), payment_date + timedelta(days=3), amount, amount, payment_date))
            
        elif check_number:
            # Match by check number
            cur.execute("""
                SELECT transaction_id
                FROM banking_transactions
                WHERE credit_amount > 0
                AND (
                    description ILIKE '%%CHECK%%' || %s || '%%'
                    OR description ILIKE '%%CHQ%%' || %s || '%%'
                    OR description ILIKE '%%CHEQUE%%' || %s || '%%'
                )
                AND ABS(credit_amount - %s) < 0.01
                AND transaction_date BETWEEN %s AND %s
                AND NOT EXISTS (
                    SELECT 1 FROM payments p 
                    WHERE p.banking_transaction_id = transaction_id
                )
                LIMIT 1
            """, (check_number, check_number, check_number, amount, 
                  payment_date - timedelta(days=7), payment_date + timedelta(days=7)))
            
        elif payment_method == 'credit_card':
            # Match to merchant deposits
            cur.execute("""
                SELECT transaction_id
                FROM banking_transactions
                WHERE credit_amount > 0
                AND transaction_date BETWEEN %s AND %s
                AND ABS(credit_amount - %s) < 0.01
                AND (
                    description ILIKE '%%VISA%%DEPOSIT%%'
                    OR description ILIKE '%%MASTERCARD%%DEPOSIT%%'
                    OR description ILIKE '%%GLOBAL%%'
                    OR description ILIKE '%%VCARD%%'
                    OR description ILIKE '%%MCARD%%'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM payments p 
                    WHERE p.banking_transaction_id = transaction_id
                )
                ORDER BY ABS(credit_amount - %s)
                LIMIT 1
            """, (payment_date - timedelta(days=3), payment_date + timedelta(days=3), amount, amount))
        
        else:
            # Unknown method - try any credit matching date+amount
            cur.execute("""
                SELECT transaction_id
                FROM banking_transactions
                WHERE credit_amount > 0
                AND transaction_date BETWEEN %s AND %s
                AND ABS(credit_amount - %s) < 0.01
                AND NOT EXISTS (
                    SELECT 1 FROM payments p 
                    WHERE p.banking_transaction_id = transaction_id
                )
                AND NOT EXISTS (
                    SELECT 1 FROM receipts r 
                    WHERE r.banking_transaction_id = transaction_id
                )
                ORDER BY ABS(credit_amount - %s), ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
                LIMIT 1
            """, (payment_date - timedelta(days=3), payment_date + timedelta(days=3), amount, amount, payment_date))
        
        match = cur.fetchone()
        if match:
            banking_txn_id = match[0]
            matched_count += 1
            
            if not dry_run:
                cur.execute("""
                    UPDATE payments 
                    SET banking_transaction_id = %s,
                        updated_at = NOW()
                    WHERE payment_id = %s
                """, (banking_txn_id, payment_id))
    
    if not dry_run and matched_count > 0:
        print(f"💾 Updated {matched_count:,} payments")
    elif matched_count > 0:
        print(f"✅ Found {matched_count:,} additional matches")
    
    return matched_count

def print_summary(cur):
    """Print final matching summary."""
    print("\n" + "="*80)
    print("FINAL PAYMENT-BANKING MATCHING STATUS")
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
    
    if match_pct >= 98:
        print(f"\n🎉 ✅ TARGET ACHIEVED: {match_pct:.1f}% ≥ 98%")
    elif match_pct >= 90:
        print(f"\n⚠️  CLOSE: {match_pct:.1f}% (Need {98-match_pct:.1f}% more)")
    else:
        print(f"\n❌ BELOW TARGET: {match_pct:.1f}% (Need {98-match_pct:.1f}% more)")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    
    dry_run = args.dry_run if args.dry_run or not args.write else False
    
    print("="*80)
    print("COMPREHENSIVE PAYMENT-BANKING MATCHING")
    print("="*80)
    print(f"Mode: {'DRY RUN' if dry_run else 'WRITE (updating database)'}")
    print("="*80)
    
    conn = get_pg_conn()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        print_summary(cur)
        
        total_matched = 0
        total_matched += match_by_charter_reserve(cur, dry_run)
        total_matched += match_remaining_by_method_and_date(cur, dry_run)
        
        if not dry_run and total_matched > 0:
            conn.commit()
            print(f"\n💾 Committed {total_matched:,} matches")
        
        print_summary(cur)
        
        if dry_run:
            print("\n💡 Run with --write to apply changes")
    
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
