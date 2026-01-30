#!/usr/bin/env python3
"""
Match unmatched payments that have account numbers to charters.
Focus on 2012 since that's the peak year.
"""

import psycopg2

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("MATCHING UNMATCHED PAYMENTS VIA ACCOUNT NUMBERS")
    print("=" * 100)
    print()
    
    # Find unmatched payments with account numbers in 2012
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.account_number,
            p.amount,
            p.payment_method,
            p.notes
        FROM payments p
        WHERE p.reserve_number IS NULL
        AND EXTRACT(YEAR FROM p.payment_date) = 2012
        AND p.account_number IS NOT NULL
        AND p.account_number != ''
        ORDER BY p.payment_date
        LIMIT 50
    """)
    
    unmatched_with_account = cur.fetchall()
    
    print(f"Unmatched 2012 payments with account numbers: {len(unmatched_with_account)}")
    print()
    
    matches_found = []
    
    print(f"{'Payment ID':<12} {'Date':<12} {'Account':<10} {'Amount':<12} {'Match Status':<50}")
    print("-" * 100)
    
    for payment_id, pay_date, account, amount, method, notes in unmatched_with_account:
        # Try to find charter with this account number and similar date/amount
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.charter_date,
                COALESCE(cc.total_charges, 0) as total_charges,
                c.balance
            FROM charters c
            LEFT JOIN (
                SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
                FROM charter_charges
                GROUP BY charter_id
            ) cc ON c.charter_id = cc.charter_id
            WHERE c.account_number = %s
            AND c.charter_date::date BETWEEN %s::date - INTERVAL '30 days' 
                                         AND %s::date + INTERVAL '30 days'
            ORDER BY ABS(EXTRACT(EPOCH FROM (c.charter_date::timestamp - %s::timestamp))) ASC
            LIMIT 5
        """, (account, pay_date, pay_date, pay_date))
        
        charters = cur.fetchall()
        
        if charters:
            best_match = None
            for charter_id, reserve_num, charter_date, total_charges, balance in charters:
                # Check if amount matches charges or balance
                if abs(float(amount) - float(total_charges)) < 1.0:
                    best_match = (charter_id, reserve_num, charter_date, total_charges, 'charges')
                    break
                elif balance and abs(float(amount) - float(balance)) < 1.0:
                    best_match = (charter_id, reserve_num, charter_date, total_charges, 'balance')
                    break
            
            if not best_match and charters:
                # Just take closest by date if no amount match
                charter_id, reserve_num, charter_date, total_charges, balance = charters[0]
                best_match = (charter_id, reserve_num, charter_date, total_charges, 'date_only')
            
            if best_match:
                charter_id, reserve_num, charter_date, total_charges, match_type = best_match
                status = f"→ Charter {charter_id} (Reserve {reserve_num}, ${total_charges:.2f}, {match_type})"
                matches_found.append((payment_id, charter_id, match_type))
            else:
                status = f"Account {account} has charters but no good match"
        else:
            status = f"No charter found for account {account}"
        
        date_str = pay_date.strftime('%Y-%m-%d') if pay_date else 'N/A'
        print(f"{payment_id:<12} {date_str:<12} {account:<10} ${float(amount):<11.2f} {status:<50}")
    
    print()
    print("=" * 100)
    print("MATCHING SUMMARY:")
    print("=" * 100)
    print()
    
    exact_matches = sum(1 for _, _, match_type in matches_found if match_type in ['charges', 'balance'])
    date_matches = sum(1 for _, _, match_type in matches_found if match_type == 'date_only')
    
    print(f"Total payments checked: {len(unmatched_with_account)}")
    print(f"Exact amount matches: {exact_matches}")
    print(f"Date proximity matches: {date_matches}")
    print(f"Total potential matches: {len(matches_found)}")
    print()
    
    if exact_matches > 0:
        print("[OK] GOOD NEWS: Found payments that match charter charges/balances exactly!")
        print()
        print("Would you like me to create a script to apply these matches? (Y/N)")
        print()
        print("Sample exact matches:")
        for payment_id, charter_id, match_type in matches_found[:10]:
            if match_type in ['charges', 'balance']:
                print(f"  UPDATE payments SET charter_id = {charter_id} WHERE payment_id = {payment_id};")
    
    # Check all 2012 unmatched with account numbers
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE charter_id IS NULL
        AND EXTRACT(YEAR FROM payment_date) = 2012
        AND account_number IS NOT NULL
        AND account_number != ''
    """)
    
    total_with_account = cur.fetchone()[0]
    
    print()
    print(f"Total 2012 unmatched with account numbers: {total_with_account}")
    print(f"Estimated matchable (based on sample): {int(total_with_account * exact_matches / len(unmatched_with_account))} payments")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
