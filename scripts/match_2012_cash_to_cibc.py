#!/usr/bin/env python3
"""
Match 2012 Cash Transactions to CIBC Banking Records

Matches the 26 unmatched cash payments (QBO deposits) to CIBC banking credit transactions
by date and amount. These are likely deposit slips recorded in QuickBooks that should
match bank deposit transactions.
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

def match_cash_payments_to_banking(cur, dry_run=True):
    """Match QBO cash deposit payments to CIBC banking credit transactions."""
    print("\n" + "="*100)
    print("MATCHING 2012 CASH PAYMENTS TO CIBC BANKING RECORDS")
    print("="*100)
    
    # Get unmatched cash payments in 2012
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.account_number,
            p.notes,
            p.reference_number
        FROM payments p
        WHERE p.payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND LOWER(p.payment_method) = 'cash'
          AND (p.charter_id IS NULL OR p.charter_id = 0)
        ORDER BY p.payment_date, p.amount DESC
    """)
    
    cash_payments = cur.fetchall()
    print(f"\nFound {len(cash_payments)} unmatched cash payments to match")
    print(f"Total amount: ${sum(p['amount'] for p in cash_payments):,.2f}")
    
    # Get CIBC banking credits in 2012 (deposits)
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.credit_amount,
            bt.description,
            bt.account_number,
            bt.balance
        FROM banking_transactions bt
        WHERE bt.transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND bt.credit_amount IS NOT NULL
          AND bt.credit_amount > 0
          AND bt.account_number IN ('0228362', '903990106011')  -- CIBC accounts
        ORDER BY bt.transaction_date, bt.credit_amount DESC
    """)
    
    banking_credits = cur.fetchall()
    print(f"\nFound {len(banking_credits)} CIBC banking credit transactions")
    print(f"Total amount: ${sum(b['credit_amount'] for b in banking_credits):,.2f}")
    
    # Match payments to banking
    matches = []
    matched_payments = set()
    matched_banking = set()
    
    print(f"\n=== Matching Strategy ===")
    print("1. Exact date + exact amount")
    print("2. Date ±3 days + exact amount")
    print("3. Date ±7 days + amount within $1.00")
    
    for payment in cash_payments:
        if payment['payment_id'] in matched_payments:
            continue
        
        best_match = None
        best_confidence = 0
        
        for banking in banking_credits:
            if banking['transaction_id'] in matched_banking:
                continue
            
            date_diff = abs((banking['transaction_date'] - payment['payment_date']).days)
            amount_diff = abs(banking['credit_amount'] - payment['amount'])
            
            confidence = 0
            match_type = None
            
            # Strategy 1: Exact date + exact amount
            if date_diff == 0 and amount_diff < 0.01:
                confidence = 100
                match_type = 'exact_date_exact_amount'
            # Strategy 2: Date ±3 days + exact amount
            elif date_diff <= 3 and amount_diff < 0.01:
                confidence = 95
                match_type = 'near_date_exact_amount'
            # Strategy 3: Date ±7 days + amount within $1
            elif date_diff <= 7 and amount_diff <= 1.00:
                confidence = 85
                match_type = 'near_date_near_amount'
            
            if confidence > best_confidence:
                best_confidence = confidence
                best_match = banking
                best_match_type = match_type
        
        if best_match and best_confidence >= 85:
            matches.append({
                'payment': payment,
                'banking': best_match,
                'confidence': best_confidence,
                'match_type': best_match_type,
                'date_diff': abs((best_match['transaction_date'] - payment['payment_date']).days),
                'amount_diff': abs(best_match['credit_amount'] - payment['amount'])
            })
            matched_payments.add(payment['payment_id'])
            matched_banking.add(best_match['transaction_id'])
    
    print(f"\n=== Match Results ===")
    print(f"Total matches found: {len(matches)}")
    print(f"Matched payment amount: ${sum(m['payment']['amount'] for m in matches):,.2f}")
    print(f"Matched banking amount: ${sum(m['banking']['credit_amount'] for m in matches):,.2f}")
    print(f"Unmatched payments: {len(cash_payments) - len(matches)}")
    
    if matches:
        print(f"\n=== Match Details ===")
        print(f"{'Payment ID':<12} {'Pay Date':<12} {'Pay Amt':>12} {'Bank Date':<12} {'Bank Amt':>12} {'Diff':>8} {'Conf':>5} {'Type':<25}")
        print("-" * 125)
        
        matches_by_confidence = sorted(matches, key=lambda x: (-x['confidence'], -x['payment']['amount']))
        
        for match in matches_by_confidence:
            p = match['payment']
            b = match['banking']
            date_diff = f"±{match['date_diff']}d"
            amt_diff = f"${match['amount_diff']:.2f}"
            
            print(f"{p['payment_id']:<12} {p['payment_date'].strftime('%Y-%m-%d'):<12} ${p['amount']:>11,.2f} "
                  f"{b['transaction_date'].strftime('%Y-%m-%d'):<12} ${b['credit_amount']:>11,.2f} "
                  f"{amt_diff:>8} {match['confidence']:>4}% {match['match_type']:<25}")
    
    # Show sample of unmatched
    unmatched_payments = [p for p in cash_payments if p['payment_id'] not in matched_payments]
    if unmatched_payments:
        print(f"\n=== Unmatched Payments (Sample) ===")
        print(f"{'Payment ID':<12} {'Date':<12} {'Amount':>12} {'Notes':<50}")
        print("-" * 90)
        for p in unmatched_payments[:10]:
            notes = (p['notes'] or '')[:47] + '...' if p['notes'] and len(p['notes']) > 50 else (p['notes'] or '')
            print(f"{p['payment_id']:<12} {p['payment_date'].strftime('%Y-%m-%d'):<12} ${p['amount']:>11,.2f} {notes:<50}")
    
    # Apply matches if in write mode
    if not dry_run and matches:
        print(f"\n=== Applying Matches ===")
        
        # Create/update income_ledger entries
        updated = 0
        ledger_created = 0
        
        for match in matches:
            p = match['payment']
            b = match['banking']
            
            # Update payment notes to indicate banking link
            cur.execute("""
                UPDATE payments
                SET notes = CASE 
                    WHEN notes IS NULL THEN %s
                    ELSE notes || ' | ' || %s
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
            """, (
                f"Matched to CIBC banking txn {b['transaction_id']} ({match['match_type']})",
                f"Matched to CIBC banking txn {b['transaction_id']} ({match['match_type']})",
                p['payment_id']
            ))
            updated += 1
            
            # Check if income_ledger entry exists for this payment
            cur.execute("""
                SELECT income_id FROM income_ledger 
                WHERE payment_id = %s
            """, (p['payment_id'],))
            
            existing_ledger = cur.fetchone()
            
            if not existing_ledger:
                # Create income_ledger entry
                cur.execute("""
                    INSERT INTO income_ledger (
                        payment_id,
                        transaction_date,
                        gross_amount,
                        net_amount,
                        description,
                        notes,
                        source_system,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 'cibc_banking_match', CURRENT_TIMESTAMP
                    )
                """, (
                    p['payment_id'],
                    p['payment_date'],
                    p['amount'],
                    p['amount'],
                    f"QBO Deposit matched to CIBC banking txn {b['transaction_id']} ({match['match_type']})",
                    f"Auto-matched: confidence={match['confidence']}%, date_diff={match['date_diff']}d, amount_diff=${match['amount_diff']:.2f}"
                ))
                ledger_created += 1
        
        print(f"\nUpdated {updated} payment records with banking links")
        print(f"Created {ledger_created} income_ledger entries")
        
        # Summary stats
        cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                COUNT(CASE WHEN notes LIKE '%Matched to CIBC banking%' THEN 1 END) as matched_to_banking,
                SUM(amount) as total_amount,
                SUM(CASE WHEN notes LIKE '%Matched to CIBC banking%' THEN amount ELSE 0 END) as matched_amount
            FROM payments
            WHERE payment_date BETWEEN '2012-01-01' AND '2012-12-31'
              AND LOWER(payment_method) = 'cash'
        """)
        
        stats = cur.fetchone()
        print(f"\n=== Updated Statistics ===")
        print(f"Total 2012 cash payments: {stats['total_payments']}")
        print(f"Matched to banking: {stats['matched_to_banking']} ({stats['matched_to_banking']/stats['total_payments']*100:.1f}%)")
        print(f"Matched amount: ${stats['matched_amount']:,.2f} of ${stats['total_amount']:,.2f}")
    
    return matches

def analyze_unmatched_banking(cur):
    """Analyze CIBC banking credits that didn't match to cash payments."""
    print("\n" + "="*100)
    print("UNMATCHED CIBC BANKING CREDITS ANALYSIS")
    print("="*100)
    
    # Get banking credits without payment matches
    cur.execute("""
        SELECT 
            bt.transaction_id,
            bt.transaction_date,
            bt.credit_amount,
            bt.description,
            bt.account_number
        FROM banking_transactions bt
        WHERE bt.transaction_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND bt.credit_amount IS NOT NULL
          AND bt.credit_amount > 0
          AND bt.account_number IN ('0228362', '903990106011')
          AND NOT EXISTS (
              SELECT 1 FROM income_ledger il
              JOIN payments p ON p.payment_id = il.payment_id
              WHERE p.notes LIKE '%CIBC banking txn ' || bt.transaction_id || '%'
          )
        ORDER BY bt.credit_amount DESC
        LIMIT 20
    """)
    
    unmatched = cur.fetchall()
    
    print(f"\nFound {len(unmatched)} high-value unmatched banking credits")
    
    if unmatched:
        print(f"\n=== Top Unmatched CIBC Credits ===")
        print(f"{'Date':<12} {'Amount':>12} {'Description':<70}")
        print("-" * 100)
        for b in unmatched:
            desc = b['description'][:67] + '...' if len(b['description']) > 70 else b['description']
            print(f"{b['transaction_date'].strftime('%Y-%m-%d'):<12} ${b['credit_amount']:>11,.2f} {desc:<70}")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Match 2012 cash transactions to CIBC banking')
    parser.add_argument('--write', action='store_true', help='Apply matches (default is dry-run)')
    parser.add_argument('--min-confidence', type=int, default=85, help='Minimum match confidence (default: 85)')
    args = parser.parse_args()
    
    dry_run = not args.write
    
    print("\n" + "="*100)
    print("2012 CASH TO CIBC BANKING MATCHER")
    print(f"Mode: {'WRITE (applying matches)' if args.write else 'DRY-RUN (preview only)'}")
    print(f"Minimum confidence: {args.min_confidence}%")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Match cash payments to banking
        matches = match_cash_payments_to_banking(cur, dry_run)
        
        # Analyze unmatched banking
        analyze_unmatched_banking(cur)
        
        # Commit if write mode
        if args.write:
            conn.commit()
            print("\n" + "="*100)
            print("MATCHES APPLIED SUCCESSFULLY")
            print("="*100)
        else:
            print("\n" + "="*100)
            print("DRY-RUN COMPLETE - No changes made")
            print("Run with --write to apply matches")
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
