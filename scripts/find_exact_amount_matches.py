#!/usr/bin/env python3
"""
Find exact amount + date matches for cash payments.
Shows the 10 potential matches identified in the analysis.
"""

import psycopg2
import os
from datetime import datetime

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
    
    print("=" * 120)
    print("CASH PAYMENT EXACT MATCHES - Amount + Date (±7 days)")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 120)
    
    # Find cash payments with exact amount + date matches
    cur.execute("""
        SELECT DISTINCT
            p.payment_id,
            p.payment_date,
            p.amount,
            p.reference_number,
            p.notes,
            c.charter_id,
            c.reserve_number,
            c.charter_date,
            c.balance,
            c.total_amount_due,
            c.client_id,
            cl.client_name,
            ABS((c.charter_date - p.payment_date)) as days_diff
        FROM payments p
        JOIN charters c ON c.charter_date BETWEEN p.payment_date - INTERVAL '7 days' 
                                              AND p.payment_date + INTERVAL '7 days'
        LEFT JOIN clients cl ON c.client_id = cl.client_id
        WHERE p.payment_method = 'cash'
        AND (p.charter_id IS NULL OR p.charter_id = 0)
        AND p.amount IS NOT NULL
        AND ABS(COALESCE(c.balance, c.total_amount_due, 0) - p.amount) < 1.0
        AND p.payment_date >= '2007-01-01'
        AND p.payment_date < '2025-01-01'
        ORDER BY p.payment_date DESC, days_diff ASC
    """)
    
    matches = cur.fetchall()
    
    print(f"\nFound {len(matches)} exact amount + date matches\n")
    
    if matches:
        print(f"{'Pay ID':<8} {'Pay Date':<12} {'Amount':<10} {'Days':<6} {'Charter':<10} {'Char Date':<12} {'Balance':<10} {'Client':<30}")
        print("-" * 120)
        
        for row in matches:
            pid, pdate, amt, ref, notes, cid, resnum, cdate, balance, total, client_id, client_name, days_diff = row
            amt_val = float(amt) if amt else 0.0
            balance_val = float(balance) if balance else float(total) if total else 0.0
            days = int(days_diff)
            
            print(f"{pid:<8} {str(pdate):<12} ${amt_val:>8.2f} {days:<6} {resnum or '':<10} {str(cdate):<12} ${balance_val:>8.2f} {(client_name or '')[:28]:<30}")
            
            if notes:
                print(f"         Notes: {notes[:100]}")
            print()
    
    print("\n" + "=" * 120)
    print("RECOMMENDED ACTION:")
    print("=" * 120)
    print("Review these matches manually for linking. Most appear to be legitimate payment-charter pairs.")
    print("=" * 120)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
