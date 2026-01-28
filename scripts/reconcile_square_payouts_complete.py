#!/usr/bin/env python3
"""
COMPLETE SQUARE PAYOUT RECONCILIATION

Square banking deposits are NET amounts:
  Banking Deposit = Customer Payments - Processing Fees - Loan Deductions

This script reconciles:
1. Square payouts → Banking deposits (NET match)
2. Square fees → Create receipts (expenses)
3. Square loan payments → Track loan repayments
4. Customer payments → Link to charters

USAGE:
    python -X utf8 scripts/reconcile_square_payouts_complete.py --dry-run
    python -X utf8 scripts/reconcile_square_payouts_complete.py --write
"""

import os
import psycopg2
from datetime import timedelta
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def match_payouts_to_banking(cur, dry_run=True):
    """Match square_payouts to banking_transactions deposits."""
    print("\n" + "="*80)
    print("1. MATCHING SQUARE PAYOUTS TO BANKING DEPOSITS")
    print("="*80)
    
    # Check if square_payouts table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'square_payouts'
        )
    """)
    
    if not cur.fetchone()[0]:
        print("❌ square_payouts table not found - cannot reconcile")
        return 0, []
    
    # Get Square payouts without banking links
    cur.execute("""
        SELECT 
            payout_id,
            payout_date,
            net_amount,
            gross_amount,
            total_fee,
            description
        FROM square_payouts
        WHERE banking_transaction_id IS NULL
        ORDER BY payout_date DESC
    """)
    
    payouts = cur.fetchall()
    print(f"Square payouts without banking links: {len(payouts):,}")
    
    if not payouts:
        print("✅ All Square payouts already matched!")
        return 0, []
    
    matched = []
    fee_receipts = []
    
    for payout_id, payout_date, net_amount, gross_amount, total_fee, description in payouts:
        # Match to banking deposit by NET amount (±$0.50) and date (±3 days)
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
            AND ABS(credit_amount - %s) < 0.50
            AND NOT EXISTS (
                SELECT 1 FROM square_payouts sp 
                WHERE sp.banking_transaction_id = transaction_id
            )
            ORDER BY ABS(credit_amount - %s), ABS(EXTRACT(EPOCH FROM (transaction_date - %s::timestamp)))
            LIMIT 1
        """, (
            payout_date - timedelta(days=3),
            payout_date + timedelta(days=3),
            net_amount,
            net_amount,
            payout_date
        ))
        
        match = cur.fetchone()
        
        if match:
            transaction_id, trans_date, credit_amount, bank_desc = match
            matched.append({
                'payout_id': payout_id,
                'transaction_id': transaction_id,
                'payout_date': payout_date,
                'trans_date': trans_date,
                'net_amount': net_amount,
                'gross_amount': gross_amount,
                'total_fee': total_fee
            })
            
            # Create receipt for Square processing fee
            if total_fee and total_fee > 0:
                fee_receipts.append({
                    'payout_id': payout_id,
                    'banking_transaction_id': transaction_id,
                    'date': trans_date,
                    'amount': total_fee,
                    'description': f"Square Processing Fees - Payout {payout_id} ({payout_date})"
                })
    
    print(f"✅ Found {len(matched):,} payout matches")
    print(f"💰 Square fees to record: {len(fee_receipts):,} receipts totaling ${sum(r['amount'] for r in fee_receipts):,.2f}")
    
    if matched and not dry_run:
        # Update square_payouts with banking_transaction_id
        for m in matched:
            cur.execute("""
                UPDATE square_payouts 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payout_id = %s
            """, (m['transaction_id'], m['payout_id']))
        
        print(f"💾 Updated {len(matched):,} payout records")
    
    # Show sample
    if matched:
        print("\n📋 Sample payout matches:")
        for m in matched[:10]:
            print(f"   Payout {m['payout_id']} ({m['payout_date']}) → Banking {m['transaction_id']} ({m['trans_date']})")
            print(f"      Net: ${m['net_amount']:,.2f} | Gross: ${m['gross_amount']:,.2f} | Fee: ${m['total_fee']:,.2f}")
    
    return len(matched), fee_receipts

def create_square_fee_receipts(cur, fee_receipts, dry_run=True):
    """Create receipts for Square processing fees."""
    print("\n" + "="*80)
    print("2. CREATING SQUARE FEE RECEIPTS")
    print("="*80)
    
    if not fee_receipts:
        print("✅ No new Square fee receipts to create")
        return 0
    
    print(f"Square fee receipts to create: {len(fee_receipts):,}")
    print(f"Total fees: ${sum(r['amount'] for r in fee_receipts):,.2f}")
    
    if not dry_run:
        created = 0
        for receipt in fee_receipts:
            # Check if receipt already exists
            cur.execute("""
                SELECT receipt_id FROM receipts
                WHERE banking_transaction_id = %s
                AND description ILIKE '%square%fee%'
                AND ABS(amount - %s) < 0.01
            """, (receipt['banking_transaction_id'], receipt['amount']))
            
            if cur.fetchone():
                continue  # Receipt already exists
            
            # Create receipt
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date,
                    amount,
                    vendor_name,
                    description,
                    category,
                    banking_transaction_id,
                    created_from_banking,
                    created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
            """, (
                receipt['date'],
                receipt['amount'],
                'SQUARE',
                receipt['description'],
                'Merchant Services Fees',
                receipt['banking_transaction_id']
            ))
            created += 1
        
        print(f"💾 Created {created:,} Square fee receipts")
        return created
    else:
        print(f"🔍 Would create {len(fee_receipts):,} Square fee receipts (dry-run mode)")
        if fee_receipts:
            print("\n📋 Sample fee receipts:")
            for r in fee_receipts[:5]:
                print(f"   ${r['amount']:,.2f} on {r['date']} - {r['description']}")
        return 0

def reconcile_square_loans(cur, dry_run=True):
    """Reconcile Square Capital loan payments."""
    print("\n" + "="*80)
    print("3. RECONCILING SQUARE CAPITAL LOANS")
    print("="*80)
    
    # Check if square_loan_payments table exists
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'square_loan_payments'
        )
    """)
    
    if not cur.fetchone()[0]:
        print("ℹ️  square_loan_payments table not found - skipping")
        return 0
    
    # Get unmatched loan payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            payment_amount,
            loan_id
        FROM square_loan_payments
        WHERE banking_transaction_id IS NULL
        ORDER BY payment_date DESC
    """)
    
    loan_payments = cur.fetchall()
    print(f"Square loan payments without banking links: {len(loan_payments):,}")
    
    if not loan_payments:
        print("✅ All Square loan payments already matched!")
        return 0
    
    matched = 0
    
    for payment_id, payment_date, payment_amount, loan_id in loan_payments:
        # Square loan payments are DEDUCTED from payouts, not separate banking transactions
        # They appear in square_payouts.loan_deduction
        # Just flag them as reconciled if payout is matched
        cur.execute("""
            SELECT sp.banking_transaction_id
            FROM square_payouts sp
            WHERE sp.payout_date = %s
            AND sp.loan_deduction >= %s - 0.01
            AND sp.loan_deduction <= %s + 0.01
            AND sp.banking_transaction_id IS NOT NULL
            LIMIT 1
        """, (payment_date, payment_amount, payment_amount))
        
        match = cur.fetchone()
        
        if match and not dry_run:
            banking_transaction_id = match[0]
            cur.execute("""
                UPDATE square_loan_payments 
                SET banking_transaction_id = %s,
                    updated_at = NOW()
                WHERE payment_id = %s
            """, (banking_transaction_id, payment_id))
            matched += 1
    
    if not dry_run and matched > 0:
        print(f"💾 Matched {matched:,} loan payments to payouts")
    elif matched > 0:
        print(f"🔍 Would match {matched:,} loan payments (dry-run mode)")
    
    return matched

def link_customer_payments_to_payouts(cur, dry_run=True):
    """Link individual customer payments to Square payouts."""
    print("\n" + "="*80)
    print("4. LINKING CUSTOMER PAYMENTS TO PAYOUTS")
    print("="*80)
    
    # Check if square_transactions exists (archived table name suggests it was removed)
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name LIKE 'square_transaction%'
        ORDER BY table_name
    """)
    
    square_tables = [row[0] for row in cur.fetchall()]
    print(f"Square transaction tables: {square_tables if square_tables else 'None found'}")
    
    if not square_tables or all('archived' in t for t in square_tables):
        print("⚠️  Square transactions table not available")
        print("ℹ️  Individual customer payment matching requires Square transaction data")
        print("ℹ️  Current matching uses payment_method = 'bank_transfer' for Square payments")
        return 0
    
    # If we have square_transactions, match them
    # This would require the table structure to be known
    print("ℹ️  Square transaction matching not implemented (table archived)")
    return 0

def print_final_summary(cur):
    """Print Square reconciliation summary."""
    print("\n" + "="*80)
    print("SQUARE RECONCILIATION SUMMARY")
    print("="*80)
    
    # Square payouts matched
    cur.execute("""
        SELECT 
            COUNT(*) as total_payouts,
            SUM(net_amount) as total_net,
            SUM(gross_amount) as total_gross,
            SUM(total_fee) as total_fees,
            COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as matched
        FROM square_payouts
    """)
    
    result = cur.fetchone()
    if result and result[0]:
        total_payouts, total_net, total_gross, total_fees, matched = result
        match_pct = (matched / total_payouts * 100) if total_payouts > 0 else 0
        
        print(f"\nSquare Payouts:")
        print(f"  Total: {total_payouts:,}")
        print(f"  Matched to banking: {matched:,} ({match_pct:.1f}%)")
        print(f"  Gross amount: ${total_gross:,.2f}")
        print(f"  Processing fees: ${total_fees:,.2f}")
        print(f"  Net deposited: ${total_net:,.2f}")
    
    # Square fee receipts
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM receipts
        WHERE vendor_name = 'SQUARE'
        AND description ILIKE '%processing%fee%'
    """)
    
    fee_count, fee_total = cur.fetchone()
    if fee_count:
        print(f"\nSquare Fee Receipts:")
        print(f"  Total receipts: {fee_count:,}")
        print(f"  Total fees: ${fee_total:,.2f}")
    
    # Square loan payments
    cur.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'square_loan_payments'
        )
    """)
    
    if cur.fetchone()[0]:
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(payment_amount) as total_amount,
                COUNT(*) FILTER (WHERE banking_transaction_id IS NOT NULL) as matched
            FROM square_loan_payments
        """)
        
        result = cur.fetchone()
        if result and result[0]:
            total_loans, total_loan_amt, matched_loans = result
            loan_match_pct = (matched_loans / total_loans * 100) if total_loans > 0 else 0
            
            print(f"\nSquare Loan Payments:")
            print(f"  Total payments: {total_loans:,}")
            print(f"  Matched: {matched_loans:,} ({loan_match_pct:.1f}%)")
            print(f"  Total amount: ${total_loan_amt:,.2f}")
    
    # Banking deposits
    cur.execute("""
        SELECT COUNT(*), SUM(credit_amount)
        FROM banking_transactions
        WHERE description ILIKE '%SQUARE%'
        AND credit_amount > 0
    """)
    
    bank_count, bank_total = cur.fetchone()
    print(f"\nBanking Square Deposits:")
    print(f"  Total deposits: {bank_count:,}")
    print(f"  Total amount: ${bank_total:,.2f}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Complete Square payout reconciliation")
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without updating database')
    parser.add_argument('--write', action='store_true', help='Apply changes to database')
    args = parser.parse_args()
    
    if not args.write and not args.dry_run:
        args.dry_run = True
    
    dry_run = args.dry_run
    
    print("="*80)
    print("COMPLETE SQUARE PAYOUT RECONCILIATION")
    print("="*80)
    print(f"Mode: {'DRY RUN (preview only)' if dry_run else '✍️  WRITE (updating database)'}")
    print("="*80)
    
    conn = get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        # Print current status
        print_final_summary(cur)
        
        # Run reconciliation
        payout_matches, fee_receipts = match_payouts_to_banking(cur, dry_run)
        fee_receipt_count = create_square_fee_receipts(cur, fee_receipts, dry_run)
        loan_matches = reconcile_square_loans(cur, dry_run)
        customer_links = link_customer_payments_to_payouts(cur, dry_run)
        
        total_changes = payout_matches + fee_receipt_count + loan_matches + customer_links
        
        if not dry_run and total_changes > 0:
            conn.commit()
            print(f"\n💾 Committed {total_changes:,} changes")
        elif total_changes > 0:
            print(f"\n🔍 Found {total_changes:,} potential changes (not applied - dry-run mode)")
        
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
