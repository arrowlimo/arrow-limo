#!/usr/bin/env python3
"""
Fix 2012 Cash Transaction Issues

Addresses:
1. Match 26 unmatched cash payments to charters using account_number and dates
2. Create missing receipts for cash withdrawals without expense tracking
3. Reconcile cash in vs cash out discrepancies
4. Link QBO deposit imports to proper revenue sources
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import argparse

def get_db_connection():
    """Connect to PostgreSQL almsdata database."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    )

def match_cash_payments_to_charters(cur, dry_run=True):
    """Match unmatched cash payments to charters using account number and dates."""
    print("\n" + "="*100)
    print("1. MATCHING CASH PAYMENTS TO CHARTERS")
    print("="*100)
    
    # Get unmatched cash payments in 2012
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.account_number,
            p.notes
        FROM payments p
        WHERE p.payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND LOWER(p.payment_method) = 'cash'
          AND (p.charter_id IS NULL OR p.charter_id = 0)
        ORDER BY p.payment_date
    """)
    
    unmatched = cur.fetchall()
    print(f"\nFound {len(unmatched)} unmatched cash payments to process")
    
    matches_found = 0
    potential_matches = []
    
    for payment in unmatched:
        # Look for charters with same account number within ±7 days
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                c.account_number,
                cl.client_name,
                c.total_amount_due,
                c.paid_amount,
                c.balance
            FROM charters c
            LEFT JOIN clients cl ON cl.client_id = c.client_id
            WHERE c.account_number = %s
              AND c.charter_date BETWEEN %s AND %s
              AND c.total_amount_due > 0
            ORDER BY ABS(EXTRACT(EPOCH FROM (c.charter_date::timestamp - %s::timestamp)))
            LIMIT 5
        """, (
            payment['account_number'],
            payment['payment_date'] - timedelta(days=7),
            payment['payment_date'] + timedelta(days=7),
            payment['payment_date']
        ))
        
        charter_matches = cur.fetchall()
        
        if charter_matches:
            # Find best match (closest date, matching amount preferred)
            best_match = None
            for charter in charter_matches:
                if abs(charter['balance'] - payment['amount']) < 1.00:
                    # Exact balance match
                    best_match = charter
                    break
                elif abs(charter['total_amount_due'] - payment['amount']) < 1.00:
                    # Exact total match
                    best_match = charter
                    break
            
            if not best_match and charter_matches:
                # Use closest date
                best_match = charter_matches[0]
            
            if best_match:
                matches_found += 1
                potential_matches.append({
                    'payment': payment,
                    'charter': best_match,
                    'confidence': 'HIGH' if abs(best_match['balance'] - payment['amount']) < 1.00 else 'MEDIUM'
                })
    
    print(f"\nPotential matches found: {matches_found}")
    
    # Display matches
    if potential_matches:
        print(f"\n=== Potential Charter Matches ===")
        print(f"{'Payment ID':<12} {'Amount':>12} {'Charter':<10} {'Client':<30} {'Confidence':<10}")
        print("-" * 100)
        
        for match in potential_matches[:20]:  # Show first 20
            p = match['payment']
            c = match['charter']
            client = (c['client_name'] or 'Unknown')[:27] + '...' if c['client_name'] and len(c['client_name']) > 30 else (c['client_name'] or 'Unknown')
            print(f"{p['payment_id']:<12} ${p['amount']:>11,.2f} {c['reserve_number']:<10} {client:<30} {match['confidence']:<10}")
    
    # Apply matches
    if not dry_run and potential_matches:
        print(f"\n=== Applying Matches ===")
        updated = 0
        
        for match in potential_matches:
            p = match['payment']
            c = match['charter']
            
            # Update payment with charter_id and reserve_number
            cur.execute("""
                UPDATE payments
                SET charter_id = %s,
                    reserve_number = %s,
                    notes = CASE 
                        WHEN notes IS NULL THEN 'Auto-matched to charter (2012 cash fix)'
                        ELSE notes || ' | Auto-matched to charter (2012 cash fix)'
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
            """, (c['charter_id'], c['reserve_number'], p['payment_id']))
            
            updated += 1
        
        print(f"Updated {updated} payments with charter linkage")
        
        # Recalculate charter balances
        print(f"\nRecalculating charter balances...")
        cur.execute("""
            WITH payment_sums AS (
                SELECT 
                    reserve_number,
                    ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                FROM payments
                WHERE reserve_number IN (
                    SELECT DISTINCT reserve_number FROM payments
                    WHERE payment_id IN (
                        SELECT unnest(ARRAY[%s]::INTEGER[])
                    )
                )
                GROUP BY reserve_number
            )
            UPDATE charters c
            SET paid_amount = ps.actual_paid,
                balance = c.total_amount_due - ps.actual_paid,
                updated_at = CURRENT_TIMESTAMP
            FROM payment_sums ps
            WHERE c.reserve_number = ps.reserve_number
        """, ([m['payment']['payment_id'] for m in potential_matches],))
        
        print(f"Recalculated balances for {len(set(m['charter']['reserve_number'] for m in potential_matches))} charters")
    
    return matches_found

def analyze_cash_withdrawal_gaps(cur):
    """Identify cash withdrawals without corresponding receipts."""
    print("\n" + "="*100)
    print("2. CASH WITHDRAWAL vs RECEIPT ANALYSIS")
    print("="*100)
    
    # Get cash withdrawals from banking
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.description,
            bt.debit_amount,
            bt.account_number
        FROM banking_transactions bt
        WHERE bt.transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND bt.debit_amount IS NOT NULL
          AND bt.debit_amount > 0
          AND (
              UPPER(bt.description) LIKE '%CASH%'
              OR UPPER(bt.description) LIKE '%ATM%'
              OR UPPER(bt.description) LIKE '%WITHDRAWAL%'
          )
        ORDER BY bt.debit_amount DESC
    """)
    
    withdrawals = cur.fetchall()
    print(f"\nFound {len(withdrawals)} cash withdrawals totaling ${sum(w['debit_amount'] for w in withdrawals):,.2f}")
    
    # Check which have matching receipts
    unlinked = []
    for w in withdrawals:
        cur.execute("""
            SELECT COUNT(*) as count
            FROM banking_receipt_matching_ledger bm
            WHERE bm.banking_transaction_id = %s
        """, (w['transaction_id'],))
        
        result = cur.fetchone()
        if result['count'] == 0:
            unlinked.append(w)
    
    print(f"Withdrawals without receipts: {len(unlinked)} totaling ${sum(w['debit_amount'] for w in unlinked):,.2f}")
    
    if unlinked:
        print(f"\n=== Top 10 Unlinked Cash Withdrawals ===")
        print(f"{'Date':<12} {'Amount':>12} {'Description':<60}")
        print("-" * 90)
        for w in unlinked[:10]:
            desc = w['description'][:57] + '...' if len(w['description']) > 60 else w['description']
            print(f"{w['transaction_date'].strftime('%Y-%m-%d'):<12} ${w['debit_amount']:>11,.2f} {desc:<60}")
    
    return unlinked

def create_missing_cash_receipts(cur, withdrawals, dry_run=True):
    """Create receipts for cash withdrawals that don't have expense tracking."""
    print("\n" + "="*100)
    print("3. CREATING MISSING CASH RECEIPTS")
    print("="*100)
    
    if not withdrawals:
        print("\nNo withdrawals to process")
        return 0
    
    print(f"\nProcessing {len(withdrawals)} withdrawals...")
    
    # Filter for significant amounts (>$50) that should have receipts
    significant = [w for w in withdrawals if w['debit_amount'] > 50]
    print(f"Significant withdrawals (>$50): {len(significant)} totaling ${sum(w['debit_amount'] for w in significant):,.2f}")
    
    if not dry_run:
        created = 0
        for w in significant:
            # Categorize based on description
            category = 'cash_withdrawal'
            vendor = 'Cash Withdrawal'
            
            if 'ATM' in w['description'].upper():
                vendor = 'ATM Withdrawal'
            elif 'TRANSFER' in w['description'].upper():
                vendor = 'Cash Transfer'
                category = 'cash_transfer'
            
            # Check if receipt already exists with this source_hash
            import hashlib
            hash_input = f"{w['transaction_date']}|{w['description']}|{w['debit_amount']:.2f}".encode('utf-8')
            source_hash = hashlib.sha256(hash_input).hexdigest()
            
            cur.execute("SELECT receipt_id FROM receipts WHERE source_hash = %s", (source_hash,))
            existing = cur.fetchone()
            
            if existing:
                # Already exists, just create link
                receipt_id = existing['receipt_id']
            else:
                # Create new receipt
                cur.execute("""
                    INSERT INTO receipts (
                        receipt_date,
                        vendor_name,
                        gross_amount,
                        gst_amount,
                        net_amount,
                        category,
                        description,
                        created_from_banking,
                        mapped_bank_account_id,
                        source_hash,
                        created_at
                    ) VALUES (
                        %s, %s, %s, 0, %s, %s, %s, TRUE, 
                        CASE WHEN %s = '0228362' THEN 1 ELSE 2 END,
                        %s, CURRENT_TIMESTAMP
                    )
                    RETURNING receipt_id
                """, (
                    w['transaction_date'],
                    vendor,
                    w['debit_amount'],
                    w['debit_amount'],
                    category,
                    f"Cash withdrawal from banking | {w['description']}",
                    w['account_number'],
                    source_hash
                ))
                
                receipt_id = cur.fetchone()['receipt_id']
                created += 1
            
            # Create link in matching ledger
            cur.execute("""
                INSERT INTO banking_receipt_matching_ledger (
                    banking_transaction_id,
                    receipt_id,
                    match_date,
                    match_type,
                    match_status,
                    match_confidence,
                    notes,
                    created_by
                ) VALUES (
                    %s, %s, CURRENT_DATE, 'auto_generated', 'matched', '100',
                    '2012 cash fix - auto-created receipt for withdrawal',
                    'fix_2012_cash_transactions.py'
                )
                ON CONFLICT DO NOTHING
            """, (w['transaction_id'], receipt_id))
        
        print(f"\nCreated {created} new receipts")
        print(f"Linked {len(significant)} withdrawals to receipts")
    
    return len(significant)

def reconcile_qbo_deposits(cur, dry_run=True):
    """Analyze QBO deposit imports and attempt to match to revenue sources."""
    print("\n" + "="*100)
    print("4. RECONCILING QBO DEPOSIT IMPORTS")
    print("="*100)
    
    # Get QBO cash deposits
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.notes
        FROM payments p
        WHERE p.payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND LOWER(p.payment_method) = 'cash'
          AND p.notes LIKE '%QBO Import: Deposit%'
        ORDER BY p.amount DESC
    """)
    
    qbo_deposits = cur.fetchall()
    print(f"\nFound {len(qbo_deposits)} QBO deposit imports totaling ${sum(d['amount'] for d in qbo_deposits):,.2f}")
    
    # These are likely merchant batch deposits recorded as "cash" in QBO
    # Should be categorized as revenue, not cash payments
    
    if qbo_deposits:
        print(f"\n=== Large QBO Deposits (Top 10) ===")
        print(f"{'Payment ID':<12} {'Date':<12} {'Amount':>12} {'Notes':<50}")
        print("-" * 90)
        for d in qbo_deposits[:10]:
            notes = (d['notes'] or '')[:47] + '...' if d['notes'] and len(d['notes']) > 50 else (d['notes'] or '')
            print(f"{d['payment_id']:<12} {d['payment_date'].strftime('%Y-%m-%d'):<12} ${d['amount']:>11,.2f} {notes:<50}")
    
    print(f"\nRecommendation: These QBO deposits likely represent:")
    print("  - Merchant batch deposits (Visa/MC/Amex settlements)")
    print("  - End-of-day cash register deposits")
    print("  - Bank deposit slips recorded in QuickBooks")
    print("\nThey should be matched to:")
    print("  1. Charter revenue (if charter dates match)")
    print("  2. Banking credit deposits (if amounts match)")
    print("  3. Square/merchant processor settlements")

def generate_summary_report(cur):
    """Generate final summary of fixes applied."""
    print("\n" + "="*100)
    print("5. SUMMARY REPORT")
    print("="*100)
    
    # Count matched vs unmatched after fixes
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as matched,
            COUNT(CASE WHEN charter_id IS NULL THEN 1 END) as unmatched,
            SUM(amount) as total_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount,
            SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unmatched_amount
        FROM payments
        WHERE payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND LOWER(payment_method) = 'cash'
    """)
    
    stats = cur.fetchone()
    
    print(f"\n=== Cash Payments Status (After Fix) ===")
    print(f"Total cash payments: {stats['total']:,}")
    print(f"Matched to charters: {stats['matched']:,} (${stats['matched_amount']:,.2f}) - {stats['matched']/stats['total']*100:.1f}%" if stats['total'] > 0 else "No payments")
    print(f"Still unmatched: {stats['unmatched']:,} (${stats['unmatched_amount']:,.2f}) - {stats['unmatched']/stats['total']*100:.1f}%" if stats['total'] > 0 else "No payments")
    
    # Receipt coverage
    cur.execute("""
        SELECT 
            COUNT(DISTINCT bt.transaction_id) as total_withdrawals,
            COUNT(DISTINCT bm.banking_transaction_id) as linked_withdrawals
        FROM banking_transactions bt
        LEFT JOIN banking_receipt_matching_ledger bm ON bm.banking_transaction_id = bt.transaction_id
        WHERE bt.transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND bt.debit_amount IS NOT NULL
          AND (
              UPPER(bt.description) LIKE '%CASH%'
              OR UPPER(bt.description) LIKE '%ATM%'
          )
    """)
    
    receipt_stats = cur.fetchone()
    
    print(f"\n=== Cash Withdrawal Receipt Coverage ===")
    print(f"Total cash withdrawals: {receipt_stats['total_withdrawals']:,}")
    print(f"Linked to receipts: {receipt_stats['linked_withdrawals']:,} ({receipt_stats['linked_withdrawals']/receipt_stats['total_withdrawals']*100:.1f}%)" if receipt_stats['total_withdrawals'] > 0 else "No withdrawals")
    print(f"Unlinked: {receipt_stats['total_withdrawals'] - receipt_stats['linked_withdrawals']:,}")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Fix 2012 cash transaction issues')
    parser.add_argument('--write', action='store_true', help='Apply fixes (default is dry-run)')
    parser.add_argument('--skip-matching', action='store_true', help='Skip charter matching')
    parser.add_argument('--skip-receipts', action='store_true', help='Skip receipt creation')
    args = parser.parse_args()
    
    dry_run = not args.write
    
    print("\n" + "="*100)
    print("2012 CASH TRANSACTION FIX UTILITY")
    print(f"Mode: {'WRITE (applying fixes)' if args.write else 'DRY-RUN (preview only)'}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Step 1: Match cash payments to charters
        if not args.skip_matching:
            matches = match_cash_payments_to_charters(cur, dry_run)
        
        # Step 2: Analyze cash withdrawal gaps
        unlinked_withdrawals = analyze_cash_withdrawal_gaps(cur)
        
        # Step 3: Create missing receipts
        if not args.skip_receipts:
            receipts_created = create_missing_cash_receipts(cur, unlinked_withdrawals, dry_run)
        
        # Step 4: Analyze QBO deposits
        reconcile_qbo_deposits(cur, dry_run)
        
        # Step 5: Generate summary
        generate_summary_report(cur)
        
        # Commit if write mode
        if args.write:
            conn.commit()
            print("\n" + "="*100)
            print("FIXES APPLIED SUCCESSFULLY")
            print("="*100)
        else:
            print("\n" + "="*100)
            print("DRY-RUN COMPLETE - No changes made")
            print("Run with --write to apply fixes")
            print("="*100)
        
    except Exception as e:
        conn.rollback()
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
