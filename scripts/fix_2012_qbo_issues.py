#!/usr/bin/env python3
"""
Fix 2012 QBO Data Issues

Actions:
1. Mark 4 duplicate QBO payments (already in verified banking)
2. Attempt to match 206 QBO payments to charters by date + account
3. Handle edge cases and create audit trail
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

def mark_duplicate_qbo_payments(cur, dry_run=True):
    """Mark the 4 QBO payments that duplicate verified banking."""
    print("\n" + "="*100)
    print("1. MARKING DUPLICATE QBO PAYMENTS")
    print("="*100)
    
    # Known duplicates from audit
    duplicate_ids = [53034, 52993, 52945, 52660]
    
    print(f"\nIdentified duplicates: {len(duplicate_ids)}")
    
    # Get details
    placeholders = ','.join(['%s'] * len(duplicate_ids))
    cur.execute(f"""
        SELECT 
            payment_id,
            payment_date,
            amount,
            payment_method,
            notes
        FROM payments
        WHERE payment_id IN ({placeholders})
    """, duplicate_ids)
    
    duplicates = cur.fetchall()
    
    print(f"\n=== Duplicate Details ===")
    print(f"{'ID':<10} {'Date':<12} {'Amount':>12} {'Method':<15} {'Notes':<50}")
    print("-" * 105)
    for dup in duplicates:
        notes = (dup['notes'] or '')[:47] + '...' if dup['notes'] and len(dup['notes']) > 50 else (dup['notes'] or '')
        print(f"{dup['payment_id']:<10} {dup['payment_date'].strftime('%Y-%m-%d'):<12} ${dup['amount']:>11,.2f} {dup['payment_method']:<15} {notes:<50}")
    
    if not dry_run:
        # Update notes to mark as duplicate
        for pid in duplicate_ids:
            cur.execute("""
                UPDATE payments
                SET notes = CASE 
                    WHEN notes IS NULL THEN 'DUPLICATE: Already in verified banking transactions'
                    ELSE notes || ' | DUPLICATE: Already in verified banking transactions'
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
            """, (pid,))
        
        print(f"\n✓ Marked {len(duplicate_ids)} payments as duplicates")
    
    return duplicate_ids

def match_qbo_to_charters(cur, dry_run=True):
    """Attempt to match QBO payments to charters."""
    print("\n" + "="*100)
    print("2. MATCHING QBO PAYMENTS TO CHARTERS")
    print("="*100)
    
    # Get QBO payments that aren't duplicates and aren't already matched
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.account_number,
            p.payment_method,
            p.notes
        FROM payments p
        WHERE p.notes LIKE '%QBO Import%'
          AND p.payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (p.charter_id IS NULL OR p.charter_id = 0)
          AND p.notes NOT LIKE '%DUPLICATE%'
        ORDER BY p.payment_date, p.amount DESC
    """)
    
    unmatched_qbo = cur.fetchall()
    print(f"\nUnmatched QBO payments: {len(unmatched_qbo)}")
    print(f"Total amount: ${sum(p['amount'] for p in unmatched_qbo):,.2f}")
    
    matches = []
    
    for payment in unmatched_qbo:
        # Look for charters with same account number within ±14 days
        # Use wider window since QBO import dates may not match charter dates exactly
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                c.account_number,
                c.total_amount_due,
                c.paid_amount,
                c.balance,
                cl.client_name
            FROM charters c
            LEFT JOIN clients cl ON cl.client_id = c.client_id
            WHERE c.account_number = %s
              AND c.charter_date BETWEEN %s AND %s
              AND c.total_amount_due > 0
            ORDER BY ABS(EXTRACT(EPOCH FROM (c.charter_date::timestamp - %s::timestamp)))
            LIMIT 10
        """, (
            payment['account_number'],
            payment['payment_date'] - timedelta(days=14),
            payment['payment_date'] + timedelta(days=14),
            payment['payment_date']
        ))
        
        charter_candidates = cur.fetchall()
        
        if charter_candidates:
            # Find best match
            best_match = None
            best_score = 0
            
            for charter in charter_candidates:
                score = 0
                date_diff = abs((charter['charter_date'] - payment['payment_date']).days)
                amount_diff = abs(charter['total_amount_due'] - payment['amount'])
                balance_diff = abs(charter['balance'] - payment['amount'])
                
                # Scoring:
                # - Exact amount match to total: +100
                # - Exact amount match to balance: +90
                # - Amount within $10: +50
                # - Date within 7 days: +20
                # - Date within 14 days: +10
                
                if amount_diff < 0.01:
                    score += 100
                elif balance_diff < 0.01:
                    score += 90
                elif amount_diff <= 10:
                    score += 50
                
                if date_diff <= 7:
                    score += 20
                elif date_diff <= 14:
                    score += 10
                
                if score > best_score:
                    best_score = score
                    best_match = charter
            
            # Only match if confidence is reasonable (score >= 60)
            if best_match and best_score >= 60:
                matches.append({
                    'payment': payment,
                    'charter': best_match,
                    'score': best_score,
                    'date_diff': abs((best_match['charter_date'] - payment['payment_date']).days),
                    'amount_diff': abs(best_match['total_amount_due'] - payment['amount'])
                })
    
    print(f"\n=== Match Results ===")
    print(f"Potential matches found: {len(matches)}")
    print(f"Matched amount: ${sum(m['payment']['amount'] for m in matches):,.2f}")
    print(f"Still unmatched: {len(unmatched_qbo) - len(matches)}")
    
    if matches:
        print(f"\n=== Top 20 Matches ===")
        print(f"{'Payment ID':<12} {'Amount':>12} {'Reserve#':<10} {'Score':>6} {'Date Diff':>10} {'Client':<30}")
        print("-" * 100)
        
        for match in sorted(matches, key=lambda x: -x['score'])[:20]:
            p = match['payment']
            c = match['charter']
            client = (c['client_name'] or 'Unknown')[:27] + '...' if c['client_name'] and len(c['client_name']) > 30 else (c['client_name'] or 'Unknown')
            print(f"{p['payment_id']:<12} ${p['amount']:>11,.2f} {c['reserve_number']:<10} {match['score']:>6} ±{match['date_diff']:>2}d       {client:<30}")
    
    # Apply matches if in write mode
    if not dry_run and matches:
        print(f"\n=== Applying Matches ===")
        
        updated = 0
        for match in matches:
            p = match['payment']
            c = match['charter']
            
            # Update payment
            cur.execute("""
                UPDATE payments
                SET charter_id = %s,
                    reserve_number = %s,
                    notes = CASE 
                        WHEN notes IS NULL THEN %s
                        ELSE notes || ' | ' || %s
                        END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
            """, (
                c['charter_id'],
                c['reserve_number'],
                f"Auto-matched to charter (score={match['score']})",
                f"Auto-matched to charter (score={match['score']})",
                p['payment_id']
            ))
            updated += 1
        
        print(f"Updated {updated} payments with charter links")
        
        # Recalculate charter balances
        reserve_numbers = list(set(m['charter']['reserve_number'] for m in matches))
        print(f"\nRecalculating balances for {len(reserve_numbers)} charters...")
        
        for reserve_num in reserve_numbers:
            cur.execute("""
                WITH payment_sums AS (
                    SELECT 
                        reserve_number,
                        ROUND(SUM(COALESCE(amount, 0))::numeric, 2) as actual_paid
                    FROM payments
                    WHERE reserve_number = %s
                    GROUP BY reserve_number
                )
                UPDATE charters c
                SET paid_amount = ps.actual_paid,
                    balance = c.total_amount_due - ps.actual_paid,
                    updated_at = CURRENT_TIMESTAMP
                FROM payment_sums ps
                WHERE c.reserve_number = ps.reserve_number
            """, (reserve_num,))
        
        print(f"✓ Updated balances for {len(reserve_numbers)} charters")
    
    return matches

def analyze_unmatched_patterns(cur):
    """Analyze patterns in still-unmatched QBO payments."""
    print("\n" + "="*100)
    print("3. UNMATCHED PAYMENT PATTERNS")
    print("="*100)
    
    # Get still-unmatched payments
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.amount,
            p.payment_method,
            p.notes
        FROM payments p
        WHERE p.notes LIKE '%QBO Import%'
          AND p.payment_date BETWEEN '2012-01-01' AND '2012-12-31'
          AND (p.charter_id IS NULL OR p.charter_id = 0)
          AND p.notes NOT LIKE '%DUPLICATE%'
        ORDER BY p.amount DESC
    """)
    
    unmatched = cur.fetchall()
    
    print(f"\nRemaining unmatched: {len(unmatched)}")
    print(f"Total amount: ${sum(p['amount'] for p in unmatched):,.2f}")
    
    if unmatched:
        # Breakdown by payment method
        by_method = {}
        for p in unmatched:
            method = p['payment_method'] or 'unknown'
            if method not in by_method:
                by_method[method] = {'count': 0, 'amount': 0}
            by_method[method]['count'] += 1
            by_method[method]['amount'] += p['amount']
        
        print(f"\n=== By Payment Method ===")
        for method, stats in sorted(by_method.items(), key=lambda x: -x[1]['amount']):
            print(f"{method:<15}: {stats['count']:>4} payments (${stats['amount']:>12,.2f})")
        
        # Show high-value unmatched
        print(f"\n=== Top 10 High-Value Unmatched ===")
        print(f"{'ID':<10} {'Date':<12} {'Amount':>12} {'Method':<15} {'Notes':<40}")
        print("-" * 95)
        for p in unmatched[:10]:
            notes = (p['notes'] or '')[:37] + '...' if p['notes'] and len(p['notes']) > 40 else (p['notes'] or '')
            print(f"{p['payment_id']:<10} {p['payment_date'].strftime('%Y-%m-%d'):<12} ${p['amount']:>11,.2f} {p['payment_method']:<15} {notes:<40}")
        
        print(f"\n=== Possible Reasons for No Match ===")
        print("- Payments for services without charter (consultations, rentals)")
        print("- Merchant fees, adjustments, or corrections")
        print("- Deposits for future charters (not yet in system)")
        print("- Payment method mismatch (cash recorded as credit_card in QBO)")

def generate_summary(cur):
    """Generate final summary of QBO data status."""
    print("\n" + "="*100)
    print("4. FINAL QBO DATA STATUS")
    print("="*100)
    
    # Get current stats
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN charter_id IS NOT NULL THEN 1 END) as matched_to_charter,
            COUNT(CASE WHEN notes LIKE '%DUPLICATE%' THEN 1 END) as marked_duplicate,
            COUNT(CASE WHEN notes LIKE '%Matched to CIBC banking%' THEN 1 END) as matched_to_banking,
            SUM(amount) as total_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount
        FROM payments
        WHERE notes LIKE '%QBO Import%'
          AND payment_date BETWEEN '2012-01-01' AND '2012-12-31'
    """)
    
    stats = cur.fetchone()
    
    print(f"\n=== Overall Statistics ===")
    print(f"Total QBO payments: {stats['total']:,}")
    print(f"Total amount: ${stats['total_amount']:,.2f}")
    print(f"")
    print(f"Matched to charters: {stats['matched_to_charter']:,} ({stats['matched_to_charter']/stats['total']*100:.1f}%)")
    print(f"Matched to banking: {stats['matched_to_banking']:,} ({stats['matched_to_banking']/stats['total']*100:.1f}%)")
    print(f"Marked as duplicates: {stats['marked_duplicate']:,}")
    print(f"Still unmatched: {stats['total'] - stats['matched_to_charter'] - stats['marked_duplicate']:,}")
    print(f"")
    print(f"Revenue matched to charters: ${stats['matched_amount']:,.2f}")
    print(f"Revenue reconciliation: {stats['matched_amount']/stats['total_amount']*100:.1f}%")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='Fix 2012 QBO data issues')
    parser.add_argument('--write', action='store_true', help='Apply fixes (default is dry-run)')
    parser.add_argument('--skip-duplicates', action='store_true', help='Skip marking duplicates')
    parser.add_argument('--skip-matching', action='store_true', help='Skip charter matching')
    args = parser.parse_args()
    
    dry_run = not args.write
    
    print("\n" + "="*100)
    print("2012 QBO DATA FIX UTILITY")
    print(f"Mode: {'WRITE (applying fixes)' if args.write else 'DRY-RUN (preview only)'}")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*100)
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Step 1: Mark duplicates
        if not args.skip_duplicates:
            mark_duplicate_qbo_payments(cur, dry_run)
        
        # Step 2: Match to charters
        if not args.skip_matching:
            matches = match_qbo_to_charters(cur, dry_run)
        
        # Step 3: Analyze unmatched
        analyze_unmatched_patterns(cur)
        
        # Step 4: Generate summary
        generate_summary(cur)
        
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
