#!/usr/bin/env python3
"""
Investigate orphan refunds - negative payments without matching positive payments.

Purpose: Analyze 10 orphan refunds totaling $-12,956 to determine:
- Why refunds exist without original payments
- If original payments are under different reserve_number
- If refunds are for cancelled charters
- If refunds should be deleted, linked, or flagged
"""

import psycopg2
import sys

def main():
    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(
        dbname='almsdata',
        user='postgres', 
        password='***REDACTED***',
        host='localhost'
    )
    pg_cur = pg_conn.cursor()
    
    # Get orphan refunds
    pg_cur.execute("""
        SELECT 
            p.payment_id,
            p.reserve_number,
            p.amount,
            p.payment_date,
            p.payment_method,
            p.payment_key,
            p.notes,
            c.charter_id,
            cl.client_name,
            c.charter_date,
            c.cancelled,
            c.total_amount_due,
            c.paid_amount,
            c.balance
        FROM payments p
        LEFT JOIN charters c ON c.reserve_number = p.reserve_number
        LEFT JOIN clients cl ON cl.client_id = c.client_id
        WHERE p.amount < 0
        ORDER BY p.amount ASC
    """)
    
    refunds = pg_cur.fetchall()
    
    print("=" * 120)
    print("ORPHAN REFUND INVESTIGATION")
    print("=" * 120)
    print()
    
    if not refunds:
        print("✓ No orphan refunds found - all negative payments have matching positive payments")
        return
    
    print(f"Found {len(refunds)} negative payment(s) totaling ${sum(r[2] for r in refunds):,.2f}")
    print()
    
    for idx, (payment_id, reserve_no, amount, pay_date, method, key, notes, 
              charter_id, client_name, charter_date, cancelled, total_due, paid_amt, balance) in enumerate(refunds, 1):
        
        print(f"\n{'=' * 120}")
        print(f"REFUND {idx}: Payment ID {payment_id}")
        print(f"{'=' * 120}")
        print(f"Reserve Number:  {reserve_no}")
        print(f"Amount:          ${amount:,.2f}")
        print(f"Payment Date:    {pay_date}")
        print(f"Payment Method:  {method}")
        print(f"Payment Key:     {key}")
        print(f"Notes:           {notes}")
        print()
        
        if charter_id:
            print(f"CHARTER INFORMATION:")
            print(f"  Charter ID:    {charter_id}")
            print(f"  Client Name:   {client_name}")
            print(f"  Charter Date:  {charter_date}")
            print(f"  Cancelled:     {'YES' if cancelled else 'NO'}")
            print(f"  Total Due:     ${total_due:,.2f}")
            print(f"  Paid Amount:   ${paid_amt:,.2f}")
            print(f"  Balance:       ${balance:,.2f}")
            print()
            
            # Check if there are any positive payments for this charter
            pg_cur.execute("""
                SELECT 
                    payment_id,
                    amount,
                    payment_date,
                    payment_method,
                    payment_key
                FROM payments
                WHERE reserve_number = %s
                AND amount > 0
                ORDER BY payment_date
            """, (reserve_no,))
            
            positive_payments = pg_cur.fetchall()
            
            if positive_payments:
                print(f"  POSITIVE PAYMENTS FOR THIS CHARTER ({len(positive_payments)}):")
                total_positive = sum(p[1] for p in positive_payments)
                for pid, amt, pdate, pmethod, pkey in positive_payments:
                    print(f"    {pdate}  ${amt:>10,.2f}  {pmethod or 'unknown':20s}  Key: {pkey or 'none'}")
                print(f"    Total positive payments: ${total_positive:,.2f}")
                print(f"    Net after refund: ${total_positive + amount:,.2f}")
            else:
                print(f"  ⚠️  NO POSITIVE PAYMENTS FOUND - This is a true orphan refund")
            
            # Check if charter is cancelled
            if cancelled:
                print(f"  ℹ️  Charter is CANCELLED - refund may be for cancelled booking")
        else:
            print(f"⚠️  NO CHARTER FOUND for reserve_number {reserve_no}")
            print(f"   This refund is not linked to any charter in the system")
        
        # Check if there are payments under a similar reserve number
        if reserve_no:
            # Try variations (e.g., 009583 vs 09583, 9583)
            variations = []
            if reserve_no.isdigit():
                num = int(reserve_no)
                variations = [
                    str(num),
                    str(num).zfill(6),
                    str(num).zfill(5),
                    str(num).zfill(4)
                ]
            
            if variations:
                pg_cur.execute("""
                    SELECT DISTINCT reserve_number, COUNT(*) as payment_count
                    FROM payments
                    WHERE reserve_number = ANY(%s)
                    AND reserve_number != %s
                    GROUP BY reserve_number
                """, (variations, reserve_no))
                
                similar_reserves = pg_cur.fetchall()
                
                if similar_reserves:
                    print(f"\n  ℹ️  SIMILAR RESERVE NUMBERS FOUND:")
                    for sim_res, count in similar_reserves:
                        print(f"    {sim_res}: {count} payment(s)")
    
    print()
    print("=" * 120)
    print("SUMMARY & RECOMMENDATIONS")
    print("=" * 120)
    print()
    print("Based on the analysis above, determine:")
    print("  1. Refunds for CANCELLED charters → likely legitimate, keep them")
    print("  2. Refunds with POSITIVE payments → net calculation correct, keep them")
    print("  3. Refunds WITHOUT charters → investigate if reserve_number is wrong")
    print("  4. True ORPHAN refunds (no positive, no charter) → may need to be deleted or researched")
    print()
    
    pg_cur.close()
    pg_conn.close()

if __name__ == "__main__":
    main()
