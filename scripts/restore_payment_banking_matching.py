#!/usr/bin/env python3
"""
RESTORE PAYMENT-BANKING MATCHING (98% Target)

This script restores the payment-banking matching work that gets lost when
sync_lms_to_postgres.py runs (because LMS doesn't have banking_transaction_id).

Matching Strategy:
1. Square deposits → payments by date ±3 days + amount match
2. E-Transfers → payments by date ±3 days + amount match
3. Cash deposits → payments by date ±3 days + amount match
4. Check deposits → payments by check number + amount
5. Credit card deposits (Global, CIBC, Scotia) → payments by date ±3 days + amount

USAGE:
    python -X utf8 scripts/restore_payment_banking_matching.py --dry-run
    python -X utf8 scripts/restore_payment_banking_matching.py --write
"""

import os
import psycopg2
from datetime import timedelta
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def match_square_deposits(cur, dry_run=True):
    """Match Square deposits to payments with payment_method = 'bank_transfer' or 'unknown'."""
    print("\n" + "="*80)
    print("1. MATCHING SQUARE DEPOSITS")
    print("="*80)
    
    # Get all Square deposits without payment linkage
    cur.execute("""
        SELECT 
            b.transaction_id,
            b.transaction_date,
            b.credit_amount,
            b.description
        FROM banking_transactions b
        WHERE b.credit_amount > 0
        AND b.description ILIKE '%SQUARE%'
        AND NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.banking_transaction_id = b.transaction_id
        )
        ORDER BY b.transaction_date DESC
    """)
    
    square_deposits = cur.fetchall()
    print(f"Square deposits without payment links: {len(square_deposits):,}")
    
    if not square_deposits:
        print("✅ All Square deposits already matched!")
        return 0
    
    matched = []
    
    for transaction_id, trans_date, amount, description in square_deposits:
        # Find payments within ±3 days with matching amount
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.reserve_number,
                p.notes
            FROM payments p
            WHERE p.banking_transaction_id IS NULL
            AND p.payment_date BETWEEN %s AND %s
            AND ABS(p.amount - %s) < 0.01
            AND (
                p.payment_method IN ('bank_transfer', 'unknown', 'credit_card')
                OR p.payment_method IS NULL
            )
            ORDER BY ABS(EXTRACT(EPOCH FROM (p.payment_date - %s::timestamp)))
            LIMIT 1
        """, (
            trans_date - timedelta(days=3),
            trans_date + timedelta(days=3),
            amount,
            trans_date
        ))
        
        match = cur.fetchone()
        
        if match:
            payment_id, payment_date, payment_amount, payment_method, reserve_number, notes = match
            matched.append((payment_id, transaction_id, reserve_number, payment_date, trans_date, amount))
    
    print(f"✅ Found {len(matched):,} Square deposit matches")
    
    if matched and not dry_run:
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched:
            cur.execute("""
                UPDATE payments 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (transaction_id, payment_id))
        
        print(f"💾 Updated {len(matched):,} payment records")
    
    # Show sample
    if matched:
        print("\n📋 Sample matches:")
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched[:10]:
            print(f"   Payment {payment_id} (Rsv {reserve_number}, {payment_date}) ↔ Banking {transaction_id} ({trans_date}) ${amount:,.2f}")
    
    return len(matched)

def match_etransfers(cur, dry_run=True):
    """Match E-Transfer deposits to payments."""
    print("\n" + "="*80)
    print("2. MATCHING E-TRANSFERS")
    print("="*80)
    
    # Get all E-Transfer deposits without payment linkage
    cur.execute("""
        SELECT 
            b.transaction_id,
            b.transaction_date,
            b.credit_amount,
            b.description
        FROM banking_transactions b
        WHERE b.credit_amount > 0
        AND (
            b.description ILIKE '%E-TRANSFER%'
            OR b.description ILIKE '%ETRANSFER%'
            OR b.description ILIKE '%EMAIL TRANSFER%'
            OR b.description ILIKE '%EMAIL TFR%'
        )
        AND NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.banking_transaction_id = b.transaction_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM receipts r 
            WHERE r.banking_transaction_id = b.transaction_id
        )
        ORDER BY b.transaction_date DESC
    """)
    
    etransfer_deposits = cur.fetchall()
    print(f"E-Transfer deposits without payment links: {len(etransfer_deposits):,}")
    
    if not etransfer_deposits:
        print("✅ All E-Transfers already matched!")
        return 0
    
    matched = []
    
    for transaction_id, trans_date, amount, description in etransfer_deposits:
        # Find payments within ±3 days with matching amount
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.reserve_number,
                p.notes
            FROM payments p
            WHERE p.banking_transaction_id IS NULL
            AND p.payment_date BETWEEN %s AND %s
            AND ABS(p.amount - %s) < 0.01
            AND (
                p.payment_method IN ('bank_transfer', 'unknown', 'e-transfer')
                OR p.payment_method IS NULL
            )
            ORDER BY ABS(EXTRACT(EPOCH FROM (p.payment_date - %s::timestamp)))
            LIMIT 1
        """, (
            trans_date - timedelta(days=3),
            trans_date + timedelta(days=3),
            amount,
            trans_date
        ))
        
        match = cur.fetchone()
        
        if match:
            payment_id, payment_date, payment_amount, payment_method, reserve_number, notes = match
            matched.append((payment_id, transaction_id, reserve_number, payment_date, trans_date, amount))
    
    print(f"✅ Found {len(matched):,} E-Transfer matches")
    
    if matched and not dry_run:
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched:
            cur.execute("""
                UPDATE payments 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (transaction_id, payment_id))
        
        print(f"💾 Updated {len(matched):,} payment records")
    
    # Show sample
    if matched:
        print("\n📋 Sample matches:")
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched[:10]:
            print(f"   Payment {payment_id} (Rsv {reserve_number}, {payment_date}) ↔ Banking {transaction_id} ({trans_date}) ${amount:,.2f}")
    
    return len(matched)

def match_cash_deposits(cur, dry_run=True):
    """Match cash deposits to payments with payment_method = 'cash'."""
    print("\n" + "="*80)
    print("3. MATCHING CASH DEPOSITS")
    print("="*80)
    
    # Get all cash deposits without payment linkage
    cur.execute("""
        SELECT 
            b.transaction_id,
            b.transaction_date,
            b.credit_amount,
            b.description
        FROM banking_transactions b
        WHERE b.credit_amount > 0
        AND (
            b.description ILIKE '%CASH DEPOSIT%'
            OR b.description ILIKE '%BRANCH DEPOSIT%'
            OR b.description ILIKE '%ABM DEPOSIT%'
            OR b.description ILIKE '%ATM DEPOSIT%'
            OR (b.description ILIKE '%DEPOSIT%' AND b.description ILIKE '%CASH%')
        )
        AND NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.banking_transaction_id = b.transaction_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM receipts r 
            WHERE r.banking_transaction_id = b.transaction_id
        )
        ORDER BY b.transaction_date DESC
    """)
    
    cash_deposits = cur.fetchall()
    print(f"Cash deposits without payment links: {len(cash_deposits):,}")
    
    if not cash_deposits:
        print("✅ All cash deposits already matched!")
        return 0
    
    matched = []
    
    for transaction_id, trans_date, amount, description in cash_deposits:
        # Find payments within ±3 days with matching amount
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.reserve_number,
                p.notes
            FROM payments p
            WHERE p.banking_transaction_id IS NULL
            AND p.payment_date BETWEEN %s AND %s
            AND ABS(p.amount - %s) < 0.01
            AND (
                p.payment_method IN ('cash', 'bank_transfer', 'unknown')
                OR p.payment_method IS NULL
            )
            ORDER BY ABS(EXTRACT(EPOCH FROM (p.payment_date - %s::timestamp)))
            LIMIT 1
        """, (
            trans_date - timedelta(days=3),
            trans_date + timedelta(days=3),
            amount,
            trans_date
        ))
        
        match = cur.fetchone()
        
        if match:
            payment_id, payment_date, payment_amount, payment_method, reserve_number, notes = match
            matched.append((payment_id, transaction_id, reserve_number, payment_date, trans_date, amount))
    
    print(f"✅ Found {len(matched):,} cash deposit matches")
    
    if matched and not dry_run:
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched:
            cur.execute("""
                UPDATE payments 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (transaction_id, payment_id))
        
        print(f"💾 Updated {len(matched):,} payment records")
    
    # Show sample
    if matched:
        print("\n📋 Sample matches:")
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched[:10]:
            print(f"   Payment {payment_id} (Rsv {reserve_number}, {payment_date}) ↔ Banking {transaction_id} ({trans_date}) ${amount:,.2f}")
    
    return len(matched)

def match_check_deposits(cur, dry_run=True):
    """Match check deposits to payments by check number."""
    print("\n" + "="*80)
    print("4. MATCHING CHECK DEPOSITS")
    print("="*80)
    
    # Get payments with check numbers but no banking link
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.check_number,
            p.reserve_number
        FROM payments p
        WHERE p.banking_transaction_id IS NULL
        AND p.check_number IS NOT NULL
        AND p.check_number != ''
        ORDER BY p.payment_date DESC
    """)
    
    check_payments = cur.fetchall()
    print(f"Payments with check numbers (no banking): {len(check_payments):,}")
    
    if not check_payments:
        print("✅ All check payments already matched!")
        return 0
    
    matched = []
    
    for payment_id, payment_date, amount, check_number, reserve_number in check_payments:
        # Find banking transaction with matching check number and amount
        cur.execute("""
            SELECT 
                b.transaction_id,
                b.transaction_date,
                b.credit_amount,
                b.description
            FROM banking_transactions b
            WHERE b.credit_amount > 0
            AND (
                b.description ILIKE %s
                OR b.description ILIKE %s
                OR b.description ILIKE %s
            )
            AND ABS(b.credit_amount - %s) < 0.01
            AND b.transaction_date BETWEEN %s AND %s
            AND NOT EXISTS (
                SELECT 1 FROM payments p2 
                WHERE p2.banking_transaction_id = b.transaction_id
            )
            ORDER BY ABS(EXTRACT(EPOCH FROM (b.transaction_date - %s::timestamp)))
            LIMIT 1
        """, (
            f'%CHECK%{check_number}%',
            f'%CHQ%{check_number}%',
            f'%CHEQUE%{check_number}%',
            amount,
            payment_date - timedelta(days=7),
            payment_date + timedelta(days=7),
            payment_date
        ))
        
        match = cur.fetchone()
        
        if match:
            transaction_id, trans_date, credit_amount, description = match
            matched.append((payment_id, transaction_id, reserve_number, payment_date, trans_date, amount, check_number))
    
    print(f"✅ Found {len(matched):,} check deposit matches")
    
    if matched and not dry_run:
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount, check_number in matched:
            cur.execute("""
                UPDATE payments 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (transaction_id, payment_id))
        
        print(f"💾 Updated {len(matched):,} payment records")
    
    # Show sample
    if matched:
        print("\n📋 Sample matches:")
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount, check_number in matched[:10]:
            print(f"   Payment {payment_id} (Rsv {reserve_number}, Check #{check_number}, {payment_date}) ↔ Banking {transaction_id} ({trans_date}) ${amount:,.2f}")
    
    return len(matched)

def match_credit_card_deposits(cur, dry_run=True):
    """Match credit card deposits (Global, CIBC, Scotia) to payments."""
    print("\n" + "="*80)
    print("5. MATCHING CREDIT CARD DEPOSITS")
    print("="*80)
    
    # Get all credit card deposits without payment linkage
    cur.execute("""
        SELECT 
            b.transaction_id,
            b.transaction_date,
            b.credit_amount,
            b.description
        FROM banking_transactions b
        WHERE b.credit_amount > 0
        AND (
            b.description ILIKE '%VISA DEPOSIT%'
            OR b.description ILIKE '%MASTERCARD DEPOSIT%'
            OR b.description ILIKE '%MC DEPOSIT%'
            OR b.description ILIKE '%AMEX DEPOSIT%'
            OR b.description ILIKE '%GLOBAL%DEPOSIT%'
            OR b.description ILIKE '%VCARD%'
            OR b.description ILIKE '%MCARD%'
            OR b.description ILIKE '%ACARD%'
            OR b.description ILIKE '%GLOBAL%VISA%'
            OR b.description ILIKE '%GLOBAL%MASTERCARD%'
            OR b.description ILIKE '%GLOBAL%AMEX%'
        )
        AND NOT EXISTS (
            SELECT 1 FROM payments p 
            WHERE p.banking_transaction_id = b.transaction_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM receipts r 
            WHERE r.banking_transaction_id = b.transaction_id
        )
        ORDER BY b.transaction_date DESC
    """)
    
    cc_deposits = cur.fetchall()
    print(f"Credit card deposits without payment links: {len(cc_deposits):,}")
    
    if not cc_deposits:
        print("✅ All credit card deposits already matched!")
        return 0
    
    matched = []
    
    for transaction_id, trans_date, amount, description, vendor_name in cc_deposits:
        # Find payments within ±3 days with matching amount
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_date,
                p.amount,
                p.payment_method,
                p.reserve_number,
                p.notes
            FROM payments p
            WHERE p.banking_transaction_id IS NULL
            AND p.payment_date BETWEEN %s AND %s
            AND ABS(p.amount - %s) < 0.01
            AND (
                p.payment_method IN ('credit_card', 'bank_transfer', 'unknown')
                OR p.payment_method IS NULL
            )
            ORDER BY ABS(EXTRACT(EPOCH FROM (p.payment_date - %s::timestamp)))
            LIMIT 1
        """, (
            trans_date - timedelta(days=3),
            trans_date + timedelta(days=3),
            amount,
            trans_date
        ))
        
        match = cur.fetchone()
        
        if match:
            payment_id, payment_date, payment_amount, payment_method, reserve_number, notes = match
            matched.append((payment_id, transaction_id, reserve_number, payment_date, trans_date, amount))
    
    print(f"✅ Found {len(matched):,} credit card deposit matches")
    
    if matched and not dry_run:
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched:
            cur.execute("""
                UPDATE payments 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (transaction_id, payment_id))
        
        print(f"💾 Updated {len(matched):,} payment records")
    
    # Show sample
    if matched:
        print("\n📋 Sample matches:")
        for payment_id, transaction_id, reserve_number, payment_date, trans_date, amount in matched[:10]:
            print(f"   Payment {payment_id} (Rsv {reserve_number}, {payment_date}) ↔ Banking {transaction_id} ({trans_date}) ${amount:,.2f}")
    
    return len(matched)

def print_final_summary(cur):
    """Print final matching statistics."""
    print("\n" + "="*80)
    print("FINAL PAYMENT-BANKING MATCHING SUMMARY")
    print("="*80)
    
    # Total payments
    cur.execute("SELECT COUNT(*), SUM(amount) FROM payments")
    total_payments, total_amount = cur.fetchone()
    
    # Payments with banking
    cur.execute("""
        SELECT COUNT(*), SUM(amount) 
        FROM payments 
        WHERE banking_transaction_id IS NOT NULL
    """)
    matched_payments, matched_amount = cur.fetchone()
    
    # Payments without banking
    unmatched_payments = total_payments - matched_payments
    unmatched_amount = total_amount - (matched_amount or 0)
    
    match_pct = (matched_payments / total_payments * 100) if total_payments > 0 else 0
    
    print(f"\nTotal Payments:     {total_payments:,} (${total_amount:,.2f})")
    print(f"Matched to Banking: {matched_payments:,} (${matched_amount:,.2f}) - {match_pct:.1f}%")
    print(f"Unmatched:          {unmatched_payments:,} (${unmatched_amount:,.2f}) - {100-match_pct:.1f}%")
    
    if match_pct >= 98:
        print(f"\n🎉 ✅ TARGET ACHIEVED: {match_pct:.1f}% ≥ 98%")
    elif match_pct >= 90:
        print(f"\n⚠️  CLOSE TO TARGET: {match_pct:.1f}% (Need {98-match_pct:.1f}% more)")
    else:
        print(f"\n❌ BELOW TARGET: {match_pct:.1f}% (Need {98-match_pct:.1f}% more)")
    
    # Breakdown by payment method
    print("\n📊 Matching by Payment Method:")
    cur.execute("""
        SELECT 
            COALESCE(payment_method, 'NULL') as method,
            COUNT(*) as total,
            SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 ELSE 0 END) as matched,
            SUM(amount) as total_amount,
            SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount
        FROM payments
        GROUP BY payment_method
        ORDER BY total DESC
    """)
    
    for method, total, matched, total_amt, matched_amt in cur.fetchall():
        match_pct_method = (matched / total * 100) if total > 0 else 0
        print(f"  {method:20s}: {matched:,}/{total:,} ({match_pct_method:5.1f}%)  ${matched_amt:,.2f}/${total_amt:,.2f}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Restore payment-banking matching (98% target)")
    parser.add_argument('--dry-run', action='store_true', help='Preview matches without updating database')
    parser.add_argument('--write', action='store_true', help='Apply matches to database')
    args = parser.parse_args()
    
    if not args.write and not args.dry_run:
        args.dry_run = True  # Default to dry-run
    
    dry_run = args.dry_run
    
    print("="*80)
    print("RESTORE PAYMENT-BANKING MATCHING")
    print("="*80)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else '✍️  WRITE (updating database)'}")
    print("="*80)
    
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        # Print current status
        print_final_summary(cur)
        
        # Run matching algorithms
        total_matched = 0
        total_matched += match_square_deposits(cur, dry_run)
        total_matched += match_etransfers(cur, dry_run)
        total_matched += match_cash_deposits(cur, dry_run)
        total_matched += match_check_deposits(cur, dry_run)
        total_matched += match_credit_card_deposits(cur, dry_run)
        
        if not dry_run:
            conn.commit()
            print(f"\n💾 Committed {total_matched:,} payment-banking matches")
        else:
            print(f"\n🔍 Found {total_matched:,} potential matches (not applied - dry-run mode)")
        
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
