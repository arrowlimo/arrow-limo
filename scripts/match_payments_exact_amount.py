"""
Match unmatched payments to charters using EXACT amount matching.

Strategy:
1. Find charters with outstanding balance
2. Match unmatched payments by EXACT amount (no tolerance)
3. Optionally filter by date proximity
4. Show confidence levels and ambiguous matches
"""

import psycopg2
from datetime import datetime, timedelta
import argparse

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    parser = argparse.ArgumentParser(description='Match payments by exact amount')
    parser.add_argument('--date-window', type=int, default=None,
                       help='Only match if payment date within N days of charter date (default: no limit)')
    parser.add_argument('--min-amount', type=float, default=0.01,
                       help='Minimum payment amount to consider (default: 0.01)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of payments to process')
    parser.add_argument('--exclude-account', action='append',
                       help='Exclude account numbers (can specify multiple times)')
    parser.add_argument('--write', action='store_true',
                       help='Apply matches to database (dry run by default)')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()

    # Build exclusion filter
    exclusion_filter = ""
    if args.exclude_account:
        excluded = "','".join(args.exclude_account)
        exclusion_filter = f"AND (p.account_number NOT IN ('{excluded}') OR p.account_number IS NULL)"

    # Get unmatched payments (excluding specified accounts)
    limit_clause = f"LIMIT {args.limit}" if args.limit else ""
    cur.execute(f"""
        SELECT payment_id, account_number, payment_date, amount, 
               payment_method, square_payment_id, notes
        FROM payments p
        WHERE reserve_number IS NULL 
          AND amount >= %s
          {exclusion_filter}
        ORDER BY payment_date DESC, amount DESC
        {limit_clause}
    """, (args.min_amount,))
    
    unmatched_payments = cur.fetchall()
    print(f"\n{'='*80}")
    print(f"EXACT AMOUNT MATCHING ANALYSIS")
    print(f"{'='*80}")
    print(f"Total unmatched payments to process: {len(unmatched_payments):,}")
    if args.exclude_account:
        print(f"Excluded accounts: {', '.join(args.exclude_account)}")
    print(f"Minimum amount: ${args.min_amount:,.2f}")
    if args.date_window:
        print(f"Date window: ±{args.date_window} days from charter date")
    else:
        print(f"Date window: No restriction")
    print(f"Mode: {'WRITE' if args.write else 'DRY RUN'}")
    print(f"{'='*80}\n")

    # Statistics
    exact_matches = []
    multiple_matches = []
    no_matches = []
    
    for payment_id, account_num, payment_date, amount, method, square_id, notes in unmatched_payments:
        # Find charters with EXACT amount match
        date_filter = ""
        params = [amount]
        
        if args.date_window:
            date_min = payment_date - timedelta(days=args.date_window)
            date_max = payment_date + timedelta(days=args.date_window)
            date_filter = "AND c.charter_date BETWEEN %s AND %s"
            params.extend([date_min, date_max])
        
        cur.execute(f"""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.account_number,
                c.charter_date,
                c.total_amount_due,
                c.balance,
                c.client_notes,
                COALESCE(
                    (SELECT SUM(amount) FROM payments WHERE charter_id = c.charter_id),
                    0
                ) as already_paid
            FROM charters c
            WHERE c.total_amount_due = %s
              {date_filter}
            ORDER BY c.charter_date DESC
        """, params)
        
        matching_charters = cur.fetchall()
        
        if len(matching_charters) == 1:
            charter_id, reserve_num, charter_acct, charter_date, total_due, balance, client_notes, already_paid = matching_charters[0]
            days_diff = abs((payment_date - charter_date).days) if charter_date else None
            
            exact_matches.append({
                'payment_id': payment_id,
                'charter_id': charter_id,
                'reserve_number': reserve_num,
                'amount': amount,
                'payment_date': payment_date,
                'charter_date': charter_date,
                'days_diff': days_diff,
                'payment_account': account_num,
                'charter_account': charter_acct,
                'balance': balance,
                'already_paid': already_paid,
                'payment_method': method
            })
            
        elif len(matching_charters) > 1:
            multiple_matches.append({
                'payment_id': payment_id,
                'amount': amount,
                'payment_date': payment_date,
                'account': account_num,
                'matches': matching_charters
            })
        else:
            no_matches.append({
                'payment_id': payment_id,
                'amount': amount,
                'payment_date': payment_date,
                'account': account_num
            })

    # Print results
    print(f"\n{'='*80}")
    print(f"MATCHING RESULTS")
    print(f"{'='*80}")
    print(f"Exact single matches: {len(exact_matches):,}")
    print(f"Multiple charter matches: {len(multiple_matches):,}")
    print(f"No matches found: {len(no_matches):,}")
    print(f"{'='*80}\n")

    # Show exact matches
    if exact_matches:
        print(f"\n{'='*80}")
        print(f"EXACT SINGLE MATCHES ({len(exact_matches):,})")
        print(f"{'='*80}\n")
        
        total_match_amount = sum(m['amount'] for m in exact_matches)
        
        for i, match in enumerate(exact_matches[:20], 1):  # Show first 20
            print(f"{i}. Payment {match['payment_id']} → Charter {match['charter_id']} (Reserve: {match['reserve_number']})")
            print(f"   Amount: ${match['amount']:,.2f}")
            print(f"   Payment Date: {match['payment_date']} | Charter Date: {match['charter_date']}")
            if match['days_diff'] is not None:
                print(f"   Date Difference: {match['days_diff']} days")
            print(f"   Payment Account: {match['payment_account']} | Charter Account: {match['charter_account']}")
            print(f"   Charter Balance: ${match['balance']:,.2f} | Already Paid: ${match['already_paid']:,.2f}")
            print(f"   Payment Method: {match['payment_method']}")
            print()
        
        if len(exact_matches) > 20:
            print(f"   ... and {len(exact_matches) - 20} more matches\n")
        
        print(f"Total amount in exact matches: ${total_match_amount:,.2f}\n")

    # Show multiple matches (ambiguous)
    if multiple_matches:
        print(f"\n{'='*80}")
        print(f"MULTIPLE CHARTER MATCHES - AMBIGUOUS ({len(multiple_matches):,})")
        print(f"{'='*80}\n")
        
        for i, amb in enumerate(multiple_matches[:10], 1):  # Show first 10
            print(f"{i}. Payment {amb['payment_id']}: ${amb['amount']:,.2f} on {amb['payment_date']}")
            print(f"   Account: {amb['account']}")
            print(f"   Matching charters ({len(amb['matches'])}):")
            for charter_id, reserve_num, charter_acct, charter_date, total_due, balance, client_notes, already_paid in amb['matches'][:5]:
                days_diff = abs((amb['payment_date'] - charter_date).days) if charter_date else None
                print(f"     - Charter {charter_id} (Reserve: {reserve_num}) on {charter_date} (±{days_diff} days)")
                print(f"       Account: {charter_acct} | Balance: ${balance:,.2f} | Paid: ${already_paid:,.2f}")
            if len(amb['matches']) > 5:
                print(f"     ... and {len(amb['matches']) - 5} more charters")
            print()
        
        if len(multiple_matches) > 10:
            print(f"   ... and {len(multiple_matches) - 10} more ambiguous payments\n")

    # Show no matches sample
    if no_matches:
        print(f"\n{'='*80}")
        print(f"NO MATCHES FOUND ({len(no_matches):,})")
        print(f"{'='*80}\n")
        print("Sample (first 10):")
        for i, nm in enumerate(no_matches[:10], 1):
            print(f"{i}. Payment {nm['payment_id']}: ${nm['amount']:,.2f} on {nm['payment_date']} (Account: {nm['account']})")
        if len(no_matches) > 10:
            print(f"   ... and {len(no_matches) - 10} more\n")

    # Apply matches if --write flag
    if args.write and exact_matches:
        print(f"\n{'='*80}")
        print(f"APPLYING {len(exact_matches)} EXACT MATCHES")
        print(f"{'='*80}\n")
        
        updated = 0
        for match in exact_matches:
            cur.execute("""
                UPDATE payments 
                SET charter_id = %s,
                    reserve_number = %s,
                    notes = CASE 
                        WHEN notes IS NULL OR notes = '' THEN 'Matched by exact amount'
                        ELSE notes || ' | Matched by exact amount'
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE payment_id = %s
            """, (match['charter_id'], match['reserve_number'], match['payment_id']))
            updated += cur.rowcount
        
        conn.commit()
        print(f"✓ Successfully updated {updated} payments with charter_id and reserve_number\n")
    elif args.write:
        print("\nNo matches to apply.\n")
    else:
        print("\nDRY RUN - Use --write to apply these matches to the database.\n")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
