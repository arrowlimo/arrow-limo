#!/usr/bin/env python3
"""
Check charters with negative balances where total_amount_due = 0.
"""

import psycopg2

def get_db_connection():
    import os
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("\n" + "="*80)
    print("CHARTERS WITH NEGATIVE BALANCE AND $0 TOTAL_AMOUNT_DUE")
    print("="*80)
    
    cur.execute("""
        SELECT 
            COUNT(*),
            SUM(ABS(balance)) as total_credits,
            SUM(paid_amount) as total_paid
        FROM charters
        WHERE balance < 0
        AND COALESCE(total_amount_due, 0) = 0
        AND cancelled = FALSE
    """)
    
    count, total_credits, total_paid = cur.fetchone()
    
    print(f"\nCharters with balance < 0 and total_due = $0: {count:,}")
    print(f"Total credits (abs value):                      ${total_credits:,.2f}")
    print(f"Total paid amount:                              ${total_paid:,.2f}")
    
    # Sample some
    cur.execute("""
        SELECT 
            ch.reserve_number,
            ch.charter_date,
            c.client_name,
            ch.total_amount_due,
            ch.paid_amount,
            ch.balance,
            ch.status,
            ch.closed,
            ch.cancelled,
            COUNT(p.payment_id) as payment_count
        FROM charters ch
        LEFT JOIN clients c ON ch.client_id = c.client_id
        LEFT JOIN payments p ON ch.charter_id = p.charter_id
        WHERE ch.balance < 0
        AND COALESCE(ch.total_amount_due, 0) = 0
        AND ch.cancelled = FALSE
        GROUP BY ch.charter_id, ch.reserve_number, ch.charter_date, c.client_name,
                 ch.total_amount_due, ch.paid_amount, ch.balance, ch.status, ch.closed, ch.cancelled
        ORDER BY ch.balance ASC
        LIMIT 20
    """)
    
    print(f"\n{'-'*80}")
    print("TOP 20 LARGEST CREDITS (Most negative):")
    print(f"{'-'*80}")
    print(f"{'Reserve':<10} {'Date':<12} {'Client':<25} {'Paid':>12} {'Balance':>12} {'#Pay':>5} Status")
    print(f"{'-'*80}")
    
    for row in cur.fetchall():
        reserve, date, client, total_due, paid, balance, status, closed, cancelled, pay_count = row
        client = (client[:23] + '..') if client and len(client) > 25 else (client or 'N/A')
        status = status or 'N/A'
        print(f"{reserve:<10} {str(date):<12} {client:<25} ${paid:>10,.2f} ${balance:>10,.2f} {pay_count:>5} {status}")
    
    print(f"\n{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
