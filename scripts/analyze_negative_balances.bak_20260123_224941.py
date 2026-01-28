#!/usr/bin/env python3
"""
Analyze charters with negative balances (credits) to identify root causes.
"""

import psycopg2
from datetime import datetime

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
    print("ANALYZING CHARTERS WITH NEGATIVE BALANCES (CREDITS)")
    print("="*80)
    
    # Overall statistics
    cur.execute("""
        SELECT 
            COUNT(*) as count,
            SUM(balance) as total_credits,
            MIN(balance) as largest_credit,
            AVG(balance) as avg_credit
        FROM charters
        WHERE balance < 0
        AND cancelled = FALSE
    """)
    
    count, total, largest, avg = cur.fetchone()
    print(f"\nTotal charters with credits:       {count:,}")
    print(f"Total credits (negative):          ${abs(total):,.2f}")
    print(f"Largest credit:                    ${abs(largest):,.2f}")
    print(f"Average credit:                    ${abs(avg):,.2f}")
    
    # Check payment counts vs balance
    cur.execute("""
        SELECT 
            ch.reserve_number,
            ch.charter_date,
            ch.total_amount_due,
            ch.paid_amount,
            ch.balance,
            COUNT(p.payment_id) as payment_count,
            SUM(p.amount) as sum_payment_amounts
        FROM charters ch
        LEFT JOIN payments p ON ch.charter_id = p.charter_id
        WHERE ch.balance < 0
        AND ch.cancelled = FALSE
        GROUP BY ch.charter_id, ch.reserve_number, ch.charter_date, 
                 ch.total_amount_due, ch.paid_amount, ch.balance
        ORDER BY ch.balance ASC
        LIMIT 20
    """)
    
    print("\n" + "-"*80)
    print("TOP 20 LARGEST CREDITS (Most Negative):")
    print("-"*80)
    print(f"{'Reserve':<10} {'Date':<12} {'Total Due':>12} {'Paid':>12} {'Balance':>12} {'#Pay':>5} {'Sum Pay':>12}")
    print("-"*80)
    
    rows = cur.fetchall()
    for row in rows:
        reserve, date, total_due, paid, balance, pay_count, sum_pay = row
        sum_pay = sum_pay or 0
        total_due = total_due or 0
        paid = paid or 0
        balance = balance or 0
        date_str = str(date) if date else 'N/A'
        print(f"{reserve:<10} {date_str:<12} ${total_due:>10,.2f} ${paid:>10,.2f} ${balance:>10,.2f} {pay_count:>5} ${sum_pay:>10,.2f}")
    
    # Check if paid_amount matches sum of payments
    print("\n" + "-"*80)
    print("PAYMENT RECONCILIATION CHECK:")
    print("-"*80)
    
    cur.execute("""
        WITH payment_sums AS (
            SELECT 
                charter_id,
                SUM(amount) as sum_payments
            FROM payments
            GROUP BY charter_id
        )
        SELECT 
            COUNT(*) as count,
            SUM(CASE WHEN ch.paid_amount != COALESCE(ps.sum_payments, 0) THEN 1 ELSE 0 END) as mismatches
        FROM charters ch
        LEFT JOIN payment_sums ps ON ch.charter_id = ps.charter_id
        WHERE ch.balance < 0
        AND ch.cancelled = FALSE
    """)
    
    total_credits, mismatches = cur.fetchone()
    print(f"Charters with credits:             {total_credits:,}")
    print(f"Mismatches (paid_amount != SUM):   {mismatches:,}")
    
    if mismatches > 0:
        print(f"\n[WARN]  {mismatches:,} charters have paid_amount that doesn't match sum of payment records!")
        
    # Check for duplicate payments by amount
    print("\n" + "-"*80)
    print("DUPLICATE PAYMENT ANALYSIS:")
    print("-"*80)
    
    cur.execute("""
        WITH payment_duplicates AS (
            SELECT 
                charter_id,
                amount,
                payment_date,
                COUNT(*) as dup_count
            FROM payments
            WHERE charter_id IS NOT NULL
            GROUP BY charter_id, amount, payment_date
            HAVING COUNT(*) > 1
        )
        SELECT 
            COUNT(DISTINCT pd.charter_id) as charters_with_dups,
            COUNT(*) as duplicate_groups,
            SUM(pd.dup_count) as total_dup_payments
        FROM payment_duplicates pd
        JOIN charters ch ON pd.charter_id = ch.charter_id
        WHERE ch.balance < 0
        AND ch.cancelled = FALSE
    """)
    
    dup_charters, dup_groups, total_dups = cur.fetchone()
    if dup_charters:
        print(f"Charters with duplicate payments:  {dup_charters:,}")
        print(f"Duplicate payment groups:          {dup_groups:,}")
        print(f"Total duplicate payment records:   {total_dups:,}")
    else:
        print("No obvious duplicate payments found (same charter_id, amount, date)")
    
    # Sample some specific cases
    print("\n" + "-"*80)
    print("SAMPLE ANALYSIS (First charter with largest credit):")
    print("-"*80)
    
    cur.execute("""
        SELECT 
            ch.reserve_number,
            ch.charter_date,
            ch.total_amount_due,
            ch.paid_amount,
            ch.balance,
            c.client_name
        FROM charters ch
        LEFT JOIN clients c ON ch.client_id = c.client_id
        WHERE ch.balance < 0
        AND ch.cancelled = FALSE
        ORDER BY ch.balance ASC
        LIMIT 1
    """)
    
    sample = cur.fetchone()
    if sample:
        reserve, date, total_due, paid, balance, client = sample
        print(f"\nReserve: {reserve}")
        print(f"Date: {date}")
        print(f"Client: {client or 'N/A'}")
        print(f"Total Due: ${total_due:,.2f}")
        print(f"Paid Amount: ${paid:,.2f}")
        print(f"Balance: ${balance:,.2f}")
        
        # Get payments for this charter
        cur.execute("""
            SELECT 
                payment_id,
                payment_date,
                amount,
                payment_method,
                notes
            FROM payments
            WHERE reserve_number = %s
            ORDER BY payment_date, payment_id
        """, (reserve,))
        
        payments = cur.fetchall()
        print(f"\nPayments ({len(payments)} records):")
        for p in payments:
            pid, pdate, amt, method, notes = p
            notes_str = (notes[:40] + '...') if notes and len(notes) > 40 else (notes or '')
            print(f"  [{pid}] {pdate} ${amt:,.2f} via {method or 'N/A'} - {notes_str}")
        
        # Get charges for this charter
        cur.execute("""
            SELECT 
                charge_id,
                description,
                amount
            FROM charter_charges
            WHERE reserve_number = %s
            ORDER BY charge_id
        """, (reserve,))
        
        charges = cur.fetchall()
        print(f"\nCharges ({len(charges)} records):")
        for c in charges:
            cid, desc, amt = c
            print(f"  [{cid}] ${amt:,.2f} - {desc}")
    
    print("\n" + "="*80)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
