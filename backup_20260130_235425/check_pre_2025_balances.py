#!/usr/bin/env python3
"""
Check how many charters prior to 2025 have balances owing.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get charters with balances owing prior to 2025
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(balance) as total_owing,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance,
            AVG(balance) as avg_balance
        FROM charters
        WHERE charter_date < '2025-01-01'
        AND balance > 0
        AND cancelled = FALSE
        AND closed = FALSE
    """)
    
    result = cur.fetchone()
    count, total, min_bal, max_bal, avg_bal = result
    
    print("\n" + "="*80)
    print("CHARTERS WITH BALANCES OWING PRIOR TO 2025")
    print("="*80)
    print(f"\nTotal charters with balance > 0:  {count:,}")
    print(f"Total amount owing:                ${total:,.2f}" if total else "Total amount owing:                $0.00")
    print(f"Smallest balance:                  ${min_bal:,.2f}" if min_bal else "Smallest balance:                  N/A")
    print(f"Largest balance:                   ${max_bal:,.2f}" if max_bal else "Largest balance:                   N/A")
    print(f"Average balance:                   ${avg_bal:,.2f}" if avg_bal else "Average balance:                   N/A")
    
    # Breakdown by year
    print("\n" + "-"*80)
    print("BREAKDOWN BY YEAR:")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as count,
            SUM(balance) as total_owing
        FROM charters
        WHERE charter_date < '2025-01-01'
        AND balance > 0
        AND cancelled = FALSE
        AND closed = FALSE
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    for row in cur.fetchall():
        year, count, total = row
        print(f"{int(year):4d}: {count:4,} charters, ${total:12,.2f} owing")
    
    # Show top 20 largest balances
    print("\n" + "-"*80)
    print("TOP 20 LARGEST BALANCES OWING (Pre-2025):")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            ch.reserve_number,
            ch.charter_date,
            c.client_name,
            ch.total_amount_due,
            ch.paid_amount,
            ch.balance,
            ch.status
        FROM charters ch
        LEFT JOIN clients c ON ch.client_id = c.client_id
        WHERE ch.charter_date < '2025-01-01'
        AND ch.balance > 0
        AND ch.cancelled = FALSE
        AND ch.closed = FALSE
        ORDER BY ch.balance DESC
        LIMIT 20
    """)
    
    print(f"{'Reserve':<10} {'Date':<12} {'Client':<30} {'Total Due':>12} {'Paid':>12} {'Balance':>12} Status")
    print("-"*110)
    
    for row in cur.fetchall():
        reserve, date, client, total_due, paid, balance, status = row
        client = client[:28] if client else 'N/A'
        status = status or 'N/A'
        print(f"{reserve:<10} {str(date):<12} {client:<30} ${total_due:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f} {status}")
    
    # Check for any with credits (negative balances)
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(balance) as total_credits
        FROM charters
        WHERE charter_date < '2025-01-01'
        AND balance < 0
        AND cancelled = FALSE
    """)
    
    credit_count, total_credits = cur.fetchone()
    
    if credit_count and credit_count > 0:
        print("\n" + "-"*80)
        print("CREDITS (NEGATIVE BALANCES):")
        print("-"*80)
        print(f"Total charters with credits:       {credit_count:,}")
        print(f"Total credits:                     ${abs(total_credits):,.2f}")
    
    print("\n" + "="*80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
