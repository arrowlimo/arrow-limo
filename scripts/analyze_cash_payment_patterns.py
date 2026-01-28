#!/usr/bin/env python3
"""
Analyze unmatched cash payment patterns to identify matching opportunities.
Focus on the 1,074 cash payments ($402,982.83) without charter links.
"""

import psycopg2
import os
from datetime import datetime, timedelta
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("UNMATCHED CASH PAYMENTS ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    # Get all unmatched cash payments
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            account_number,
            reserve_number,
            amount,
            reference_number,
            notes,
            client_id
        FROM payments
        WHERE payment_method = 'cash'
        AND (charter_id IS NULL OR charter_id = 0)
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        ORDER BY payment_date DESC, amount DESC
    """)
    
    cash_payments = cur.fetchall()
    print(f"\n### OVERVIEW ###")
    print(f"Total unmatched cash payments: {len(cash_payments)}")
    print(f"Total amount: ${sum(p[4] for p in cash_payments if p[4]):,.2f}\n")
    
    # Pattern 1: Payments with account_number
    with_account = [p for p in cash_payments if p[2]]
    print(f"\n### PATTERN 1: HAS ACCOUNT NUMBER ###")
    print(f"Count: {len(with_account)} payments")
    print(f"Amount: ${sum(p[4] for p in with_account if p[4]):,.2f}")
    
    if with_account:
        # Check if these account numbers exist in charters
        account_numbers = list(set(p[2] for p in with_account if p[2]))
        placeholders = ','.join(['%s'] * len(account_numbers))
        cur.execute(f"""
            SELECT DISTINCT account_number 
            FROM charters 
            WHERE account_number IN ({placeholders})
        """, account_numbers)
        
        matching_accounts = {row[0] for row in cur.fetchall()}
        print(f"Account numbers that exist in charters: {len(matching_accounts)}/{len(account_numbers)}")
        
        # Sample account number matches
        print(f"\nSample payments with account numbers (first 20):")
        print(f"{'ID':<8} {'Date':<12} {'Account':<12} {'Amount':<12} {'Notes':<50}")
        print("-" * 100)
        for p in with_account[:20]:
            pid, pdate, acct, resnum, amt, ref, notes, cid = p
            amt_val = float(amt) if amt else 0.0
            notes_str = (notes or '')[:47] + '...' if notes and len(notes) > 50 else (notes or '')
            has_match = '✓' if acct in matching_accounts else '✗'
            print(f"{pid:<8} {str(pdate):<12} {acct or '':<12} ${amt_val:>9.2f}  {has_match} {notes_str}")
    
    # Pattern 2: Payments with reserve_number
    with_reserve = [p for p in cash_payments if p[3]]
    print(f"\n\n### PATTERN 2: HAS RESERVE NUMBER ###")
    print(f"Count: {len(with_reserve)} payments")
    print(f"Amount: ${sum(p[4] for p in with_reserve if p[4]):,.2f}")
    
    if with_reserve:
        print(f"\nSample payments with reserve numbers (first 20):")
        print(f"{'ID':<8} {'Date':<12} {'Reserve':<12} {'Amount':<12} {'Notes':<50}")
        print("-" * 100)
        for p in with_reserve[:20]:
            pid, pdate, acct, resnum, amt, ref, notes, cid = p
            amt_val = float(amt) if amt else 0.0
            notes_str = (notes or '')[:47] + '...' if notes and len(notes) > 50 else (notes or '')
            print(f"{pid:<8} {str(pdate):<12} {resnum or '':<12} ${amt_val:>9.2f}  {notes_str}")
    
    # Pattern 3: Payments with client_id
    with_client = [p for p in cash_payments if p[7]]
    print(f"\n\n### PATTERN 3: HAS CLIENT ID ###")
    print(f"Count: {len(with_client)} payments")
    print(f"Amount: ${sum(p[4] for p in with_client if p[4]):,.2f}")
    
    if with_client:
        # Find charters for these clients around payment dates
        print(f"\nChecking for charter opportunities (date +/- 30 days)...")
        
        matches_found = 0
        for p in with_client[:10]:  # Sample first 10
            pid, pdate, acct, resnum, amt, ref, notes, cid = p
            
            # Find charters for this client within date range
            cur.execute("""
                SELECT charter_id, reserve_number, charter_date, balance, total_amount_due
                FROM charters
                WHERE client_id = %s
                AND charter_date BETWEEN %s AND %s
                AND (balance > 0 OR balance IS NULL OR total_amount_due > 0)
                ORDER BY ABS(EXTRACT(EPOCH FROM (charter_date - %s)))
                LIMIT 3
            """, (cid, pdate - timedelta(days=30), pdate + timedelta(days=30), pdate))
            
            charter_matches = cur.fetchall()
            if charter_matches:
                matches_found += 1
                print(f"\nPayment {pid} (${amt}, {pdate}):")
                for charter_id, res_num, c_date, balance, total in charter_matches:
                    days_diff = abs((c_date - pdate).days)
                    print(f"  → Charter {res_num} ({c_date}) - Balance: ${balance}, Days: {days_diff}")
        
        print(f"\nPotential matches found: {matches_found}/{min(10, len(with_client))} sampled")
    
    # Pattern 4: No identifiers at all
    no_identifiers = [p for p in cash_payments if not p[2] and not p[3] and not p[7]]
    print(f"\n\n### PATTERN 4: NO IDENTIFIERS (account/reserve/client) ###")
    print(f"Count: {len(no_identifiers)} payments")
    print(f"Amount: ${sum(p[4] for p in no_identifiers if p[4]):,.2f}")
    
    # Pattern 5: Amount analysis - common amounts
    amounts = defaultdict(int)
    for p in cash_payments:
        if p[4]:
            amt_rounded = round(float(p[4]), -1)  # Round to nearest $10
            amounts[amt_rounded] += 1
    
    print(f"\n\n### PATTERN 5: COMMON AMOUNTS (rounded to $10) ###")
    print(f"{'Amount Range':<20} {'Count':<10} {'Potential':<50}")
    print("-" * 80)
    
    common_amounts = sorted(amounts.items(), key=lambda x: x[1], reverse=True)[:15]
    for amt, count in common_amounts:
        print(f"${amt:>7.0f}            {count:<10} {count} payments at this amount")
    
    # Yearly distribution
    print(f"\n\n### YEARLY DISTRIBUTION ###")
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as count,
            COALESCE(SUM(amount), 0) as total
        FROM payments
        WHERE payment_method = 'cash'
        AND (charter_id IS NULL OR charter_id = 0)
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year DESC
    """)
    
    yearly = cur.fetchall()
    print(f"{'Year':<10} {'Count':<10} {'Amount':<15}")
    print("-" * 40)
    for year, count, total in yearly:
        print(f"{int(year):<10} {count:<10} ${total:>12,.2f}")
    
    # Check for potential date-based matching opportunities
    print(f"\n\n### MATCHING OPPORTUNITIES ANALYSIS ###")
    
    # Opportunity 1: Account + Date matching
    cur.execute("""
        SELECT COUNT(DISTINCT p.payment_id)
        FROM payments p
        WHERE p.payment_method = 'cash'
        AND (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.account_number IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM charters c
            WHERE c.account_number = p.account_number
            AND c.charter_date BETWEEN p.payment_date - INTERVAL '60 days' 
                                   AND p.payment_date + INTERVAL '30 days'
            AND (c.balance > 0 OR c.total_amount_due > 0)
        )
    """)
    account_date_matches = cur.fetchone()[0]
    print(f"Account + Date matching (±60/30 days): {account_date_matches} potential matches")
    
    # Opportunity 2: Client + Date matching
    cur.execute("""
        SELECT COUNT(DISTINCT p.payment_id)
        FROM payments p
        WHERE p.payment_method = 'cash'
        AND (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.client_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM charters c
            WHERE c.client_id = p.client_id
            AND c.charter_date BETWEEN p.payment_date - INTERVAL '60 days' 
                                   AND p.payment_date + INTERVAL '30 days'
            AND (c.balance > 0 OR c.total_amount_due > 0)
        )
    """)
    client_date_matches = cur.fetchone()[0]
    print(f"Client + Date matching (±60/30 days): {client_date_matches} potential matches")
    
    # Opportunity 3: Amount + Date fuzzy matching
    cur.execute("""
        SELECT COUNT(DISTINCT p.payment_id)
        FROM payments p
        WHERE p.payment_method = 'cash'
        AND (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.amount IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM charters c
            WHERE c.charter_date BETWEEN p.payment_date - INTERVAL '7 days' 
                                     AND p.payment_date + INTERVAL '7 days'
            AND ABS(COALESCE(c.balance, c.total_amount_due, 0) - p.amount) < 1.0
        )
    """)
    amount_date_matches = cur.fetchone()[0]
    print(f"Amount + Date exact match (±7 days): {amount_date_matches} potential matches")
    
    print("\n" + "=" * 100)
    print("RECOMMENDATIONS:")
    print("=" * 100)
    print("1. Create account + date matching script (highest confidence)")
    print("2. Create client + date matching script (medium confidence)")
    print("3. Manual review for legacy 2007-2008 entries (646 payments, $242K)")
    print("4. Consider write-off policy for payments without ANY identifiers")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
