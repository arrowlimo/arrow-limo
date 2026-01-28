"""
Match unmatched payments to charters using multiple strategies.

Strategy Priority:
1. Direct reserve number match (if any exist)
2. Account number + date ±7 days + amount ±5%
3. Square payment with last 4 for disambiguation
4. Flag for manual review

Usage:
  python match_payments_to_charters.py              # Dry run
  python match_payments_to_charters.py --write      # Apply matches
"""

import psycopg2
import argparse
from datetime import datetime, timedelta

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

def find_charter_matches(payment, cur):
    """Find potential charter matches for a payment."""
    pid = payment['payment_id']
    account = payment['account_number']
    amount = payment['amount']
    pdate = payment['payment_date']
    reserve = payment['reserve_number']
    square_last4 = payment['square_last4']
    
    matches = []
    
    # Strategy 1: Direct reserve number match
    if reserve:
        cur.execute("""
            SELECT charter_id, reserve_number, charter_date, rate, balance,
                   account_number, client_id
            FROM charters
            WHERE reserve_number = %s
        """, (reserve,))
        results = cur.fetchall()
        if results:
            for row in results:
                matches.append({
                    'charter_id': row[0],
                    'reserve_number': row[1],
                    'charter_date': row[2],
                    'charter_rate': row[3],
                    'balance': row[4],
                    'account_number': row[5],
                    'client_id': row[6],
                    'strategy': 'reserve_direct',
                    'confidence': 'HIGH'
                })
            return matches
    
    # Strategy 2: Account number + date ±7 days + amount ±5%
    if account and pdate and amount and amount > 0:
        date_min = pdate - timedelta(days=7)
        date_max = pdate + timedelta(days=7)
        amount_min = float(amount) * 0.95
        amount_max = float(amount) * 1.05
        
        cur.execute("""
            SELECT charter_id, reserve_number, charter_date, rate, balance,
                   account_number, client_id
            FROM charters
            WHERE account_number = %s
            AND charter_date BETWEEN %s AND %s
            AND rate BETWEEN %s AND %s
            AND charter_id NOT IN (
                SELECT DISTINCT charter_id 
                FROM payments 
                WHERE reserve_number IS NOT NULL
            )
        """, (account, date_min, date_max, amount_min, amount_max))
        
        results = cur.fetchall()
        if results:
            for row in results:
                days_diff = abs((row[2] - pdate).days)
                amount_diff = abs(float(row[3]) - float(amount))
                confidence = 'HIGH' if days_diff <= 3 and amount_diff < 1 else 'MEDIUM'
                
                matches.append({
                    'charter_id': row[0],
                    'reserve_number': row[1],
                    'charter_date': row[2],
                    'charter_rate': row[3],
                    'balance': row[4],
                    'account_number': row[5],
                    'client_id': row[6],
                    'strategy': 'account_date_amount',
                    'confidence': confidence,
                    'days_diff': days_diff,
                    'amount_diff': amount_diff
                })
    
    # If multiple matches and have Square last 4, use it to narrow down
    if len(matches) > 1 and square_last4:
        # Check which charter has payment with same last 4
        filtered_matches = []
        for match in matches:
            cur.execute("""
                SELECT COUNT(*) 
                FROM payments 
                WHERE charter_id = %s 
                AND square_last4 = %s
            """, (match['charter_id'], square_last4))
            
            if cur.fetchone()[0] > 0:
                match['square_last4_match'] = True
                match['confidence'] = 'HIGH'
                filtered_matches.append(match)
        
        if filtered_matches:
            matches = filtered_matches
    
    return matches

def main():
    parser = argparse.ArgumentParser(description='Match payments to charters')
    parser.add_argument('--write', action='store_true', help='Apply matches to database')
    parser.add_argument('--limit', type=int, help='Limit number of payments to process')
    args = parser.parse_args()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("PAYMENT-CHARTER MATCHING - DRY RUN" if not args.write else "PAYMENT-CHARTER MATCHING - APPLYING CHANGES")
    print("=" * 100)
    
    # Get unmatched payments with identifiers
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""
    
    cur.execute(f"""
        SELECT payment_id, account_number, reserve_number, amount, payment_date,
               square_payment_id, square_last4, square_card_brand, payment_method
        FROM payments
        WHERE reserve_number IS NULL
        AND (account_number IS NOT NULL OR reserve_number IS NOT NULL OR square_payment_id IS NOT NULL)
        AND amount > 0
        ORDER BY amount DESC
        {limit_clause}
    """)
    
    unmatched_payments = cur.fetchall()
    print(f"\nFound {len(unmatched_payments)} unmatched payments with identifiers")
    
    # Statistics
    stats = {
        'total_processed': 0,
        'single_match_high': 0,
        'single_match_medium': 0,
        'multiple_matches': 0,
        'no_matches': 0,
        'applied': 0
    }
    
    # Store matches for reporting
    single_matches = []
    multiple_matches = []
    no_matches = []
    
    print("\nProcessing payments...")
    print("-" * 100)
    
    for row in unmatched_payments:
        payment = {
            'payment_id': row[0],
            'account_number': row[1],
            'reserve_number': row[2],
            'amount': row[3],
            'payment_date': row[4],
            'square_payment_id': row[5],
            'square_last4': row[6],
            'square_card_brand': row[7],
            'payment_method': row[8]
        }
        
        stats['total_processed'] += 1
        matches = find_charter_matches(payment, cur)
        
        if len(matches) == 1:
            match = matches[0]
            if match['confidence'] == 'HIGH':
                stats['single_match_high'] += 1
            else:
                stats['single_match_medium'] += 1
            
            single_matches.append((payment, match))
            
            # Apply if high confidence and --write flag
            if args.write and match['confidence'] == 'HIGH':
                cur.execute("""
                    UPDATE payments
                    SET charter_id = %s,
                        notes = COALESCE(notes, '') || 
                                CASE WHEN notes IS NULL OR notes = '' THEN '' ELSE ' | ' END ||
                                %s
                    WHERE payment_id = %s
                """, (
                    match['charter_id'],
                    f"Matched via {match['strategy']} (confidence: {match['confidence']})",
                    payment['payment_id']
                ))
                stats['applied'] += 1
        
        elif len(matches) > 1:
            stats['multiple_matches'] += 1
            multiple_matches.append((payment, matches))
        
        else:
            stats['no_matches'] += 1
            no_matches.append(payment)
    
    # Report
    print("\n" + "=" * 100)
    print("MATCHING STATISTICS")
    print("=" * 100)
    print(f"Total processed: {stats['total_processed']}")
    print(f"Single match (HIGH confidence): {stats['single_match_high']}")
    print(f"Single match (MEDIUM confidence): {stats['single_match_medium']}")
    print(f"Multiple matches (need review): {stats['multiple_matches']}")
    print(f"No matches found: {stats['no_matches']}")
    
    if args.write:
        print(f"\n✓ Applied {stats['applied']} high-confidence matches")
        conn.commit()
    else:
        print("\n⚠ DRY RUN - No changes applied. Use --write to apply matches.")
    
    # Show samples
    if single_matches:
        print("\n" + "=" * 100)
        print(f"SAMPLE SINGLE MATCHES (showing first 10 of {len(single_matches)})")
        print("=" * 100)
        for payment, match in single_matches[:10]:
            print(f"\nPayment {payment['payment_id']}: ${float(payment['amount']):,.2f} on {payment['payment_date']}")
            print(f"  Account: {payment['account_number']}")
            print(f"  → Charter {match['charter_id']} (Reserve {match['reserve_number']})")
            print(f"  Strategy: {match['strategy']} | Confidence: {match['confidence']}")
            if 'days_diff' in match:
                print(f"  Date diff: {match['days_diff']} days | Amount diff: ${match['amount_diff']:.2f}")
    
    if multiple_matches:
        print("\n" + "=" * 100)
        print(f"SAMPLE MULTIPLE MATCHES (showing first 5 of {len(multiple_matches)})")
        print("=" * 100)
        for payment, matches in multiple_matches[:5]:
            print(f"\nPayment {payment['payment_id']}: ${float(payment['amount']):,.2f} on {payment['payment_date']}")
            print(f"  Account: {payment['account_number']}")
            print(f"  → {len(matches)} potential charters:")
            for match in matches:
                print(f"     Charter {match['charter_id']} (Reserve {match['reserve_number']}) - {match['confidence']}")
    
    if no_matches:
        print("\n" + "=" * 100)
        print(f"SAMPLE NO MATCHES (showing first 10 of {len(no_matches)})")
        print("=" * 100)
        for payment in no_matches[:10]:
            print(f"Payment {payment['payment_id']}: ${float(payment['amount']) if payment['amount'] else 0:,.2f}")
            print(f"  Date: {payment['payment_date']}, Account: {payment['account_number']}")
            print(f"  Method: {payment['payment_method']}, Square: {payment['square_payment_id'][:20] if payment['square_payment_id'] else 'None'}")
    
    cur.close()
    conn.close()
    
    print("\n" + "=" * 100)
    if args.write:
        print("MATCHING COMPLETE")
    else:
        print("NEXT STEP: Review results, then run with --write to apply high-confidence matches")
    print("=" * 100)

if __name__ == '__main__':
    main()
