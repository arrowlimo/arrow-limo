#!/usr/bin/env python3
"""
Check specific charter 019466 to understand the duplicate payment issue.
"""

import psycopg2

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
    
    reserve = '019466'
    
    print(f"\n{'='*80}")
    print(f"DETAILED ANALYSIS OF CHARTER {reserve}")
    print(f"{'='*80}")
    
    # Get charter details
    cur.execute("""
        SELECT 
            charter_id, reserve_number, charter_date,
            total_amount_due, paid_amount, balance,
            status, closed, cancelled
        FROM charters
        WHERE reserve_number = %s
    """, (reserve,))
    
    charter = cur.fetchone()
    if not charter:
        print(f"Charter {reserve} not found!")
        return
    
    charter_id, reserve, date, total_due, paid, balance, status, closed, cancelled = charter
    
    print(f"\nCharter ID: {charter_id}")
    print(f"Reserve: {reserve}")
    print(f"Date: {date}")
    print(f"Total Due: ${total_due:,.2f}")
    print(f"Paid Amount: ${paid:,.2f}")
    print(f"Balance: ${balance:,.2f}")
    print(f"Status: {status}")
    print(f"Closed: {closed}")
    print(f"Cancelled: {cancelled}")
    
    # Get all payments
    cur.execute("""
        SELECT 
            payment_id,
            charter_id,
            reserve_number,
            payment_date,
            amount,
            payment_method,
            notes,
            created_at
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, payment_id
    """, (reserve,))
    
    payments = cur.fetchall()
    print(f"\n{'-'*80}")
    print(f"PAYMENTS ({len(payments)} records):")
    print(f"{'-'*80}")
    
    total_payments = 0
    for p in payments:
        pid, cid, res, pdate, amt, method, notes, created = p
        total_payments += amt
        notes_str = (notes[:60] + '...') if notes and len(notes) > 60 else (notes or '')
        print(f"\nPayment ID: {pid}")
        print(f"  Charter ID: {cid}")
        print(f"  Date: {pdate}")
        print(f"  Amount: ${amt:,.2f}")
        print(f"  Method: {method or 'N/A'}")
        print(f"  Created: {created}")
        print(f"  Notes: {notes_str}")
    
    print(f"\nTotal from payment records: ${total_payments:,.2f}")
    print(f"Paid amount in charter: ${paid:,.2f}")
    print(f"Difference: ${paid - total_payments:,.2f}")
    
    # Check for duplicate payment patterns
    if len(payments) > 1:
        print(f"\n{'-'*80}")
        print("DUPLICATE ANALYSIS:")
        print(f"{'-'*80}")
        
        # Group by amount and date
        from collections import defaultdict
        groups = defaultdict(list)
        for p in payments:
            pid, cid, res, pdate, amt, method, notes, created = p
            key = (amt, pdate)
            groups[key].append(pid)
        
        for key, pids in groups.items():
            if len(pids) > 1:
                amt, pdate = key
                print(f"\nDuplicate group: ${amt:,.2f} on {pdate}")
                print(f"  Payment IDs: {pids}")
    
    # Get charges
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
    print(f"\n{'-'*80}")
    print(f"CHARGES ({len(charges)} records):")
    print(f"{'-'*80}")
    
    total_charges = 0
    for c in charges:
        cid, desc, amt = c
        total_charges += amt
        print(f"  [{cid}] ${amt:,.2f} - {desc}")
    
    print(f"\nTotal from charges: ${total_charges:,.2f}")
    print(f"Total due in charter: ${total_due:,.2f}")
    print(f"Difference: ${total_due - total_charges:,.2f}")
    
    print(f"\n{'='*80}\n")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
