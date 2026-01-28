#!/usr/bin/env python3
"""
Check if Cash Receipts Report data can help match unmatched payments.
Looking at American Express entries from the screenshot.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REMOVED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("CASH RECEIPTS REPORT - MATCHING ANALYSIS")
    print("=" * 100)
    print()
    
    # Sample entries from the screenshot (American Express 2012)
    sample_entries = [
        ('2012-01-02', '01803', '005689', 517.50),
        ('2012-01-03', '02173', '005656', 267.50),
        ('2012-01-08', '02173', '005657', 472.50),
        ('2012-01-15', '02269', '002732', 1148.38),
        ('2012-01-17', '01419', '005712', 500.00),
        ('2012-01-14', '02269', '005761', 15.00),
        ('2012-01-14', '02269', '005762', 32.00),
        ('2012-01-27', '01419', '005794', 250.00),
        ('2012-01-30', '02233', '005869', 231.00),
        ('2012-01-30', '01120', '005811', 15.00),
    ]
    
    print("Checking sample American Express entries from Cash Receipts Report:")
    print()
    print(f"{'Date':<12} {'Account':<10} {'Reserve':<10} {'Amount':<12} {'Status':<40}")
    print("-" * 100)
    
    matches_found = 0
    no_payment_found = 0
    already_matched = 0
    can_match = 0
    
    for date_str, account, reserve, amount in sample_entries:
        # Check if we have an unmatched payment for this amount and date
        cur.execute("""
            SELECT 
                p.payment_id,
                p.charter_id,
                p.account_number,
                p.reserve_number,
                p.amount
            FROM payments p
            WHERE p.payment_date = %s
            AND ABS(p.amount - %s) < 0.01
            ORDER BY p.payment_id
            LIMIT 1
        """, (date_str, amount))
        
        payment = cur.fetchone()
        
        if payment:
            payment_id, charter_id, pay_account, pay_reserve, pay_amount = payment
            if charter_id and charter_id != 0:
                status = f"[OK] Already matched (Payment {payment_id} → Charter {charter_id})"
                already_matched += 1
            else:
                # Check if charter exists for this account/reserve
                cur.execute("""
                    SELECT charter_id, reserve_number
                    FROM charters
                    WHERE (account_number = %s OR reserve_number = %s)
                    AND charter_date::date BETWEEN %s::date - INTERVAL '7 days' 
                                                AND %s::date + INTERVAL '7 days'
                    LIMIT 1
                """, (account, reserve, date_str, date_str))
                
                charter = cur.fetchone()
                if charter:
                    charter_id, charter_reserve = charter
                    status = f"🔧 CAN MATCH: Payment {payment_id} → Charter {charter_id} (Reserve {charter_reserve})"
                    can_match += 1
                else:
                    status = f"[WARN] Payment {payment_id} exists but no matching charter found"
                    no_payment_found += 1
        else:
            status = "[FAIL] No payment record found for this date/amount"
            no_payment_found += 1
        
        print(f"{date_str:<12} {account:<10} {reserve:<10} ${amount:<11.2f} {status:<40}")
    
    print()
    print("=" * 100)
    print("SUMMARY:")
    print("=" * 100)
    print()
    print(f"Sample entries checked: {len(sample_entries)}")
    print(f"Already matched: {already_matched}")
    print(f"Can be matched: {can_match}")
    print(f"No payment/charter: {no_payment_found}")
    print()
    
    if can_match > 0:
        print(f"[OK] Found {can_match} entries that CAN be matched!")
        print()
    
    # Now check all unmatched payments from 2012 that might match charters
    print("=" * 100)
    print("CHECKING ALL 2012 UNMATCHED PAYMENTS:")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            p.account_number,
            p.reserve_number,
            p.amount,
            p.payment_method
        FROM payments p
        WHERE p.charter_id IS NULL
        AND EXTRACT(YEAR FROM p.payment_date) = 2012
        ORDER BY p.payment_date
    """)
    
    unmatched_2012 = cur.fetchall()
    print(f"Total unmatched 2012 payments: {len(unmatched_2012):,}")
    print()
    
    # Try to match by account + date + amount
    potential_matches = 0
    
    print("Scanning for potential matches (account + date ±7 days + amount)...")
    print()
    
    for payment_id, pay_date, account, reserve, amount, method in unmatched_2012[:100]:  # Sample first 100
        if not pay_date or not amount:
            continue
            
        # Look for charter with matching account and date within 7 days
        cur.execute("""
            SELECT 
                c.charter_id,
                c.reserve_number,
                c.account_number,
                c.charter_date,
                cc.total_charges
            FROM charters c
            LEFT JOIN (
                SELECT charter_id, SUM(COALESCE(amount, 0)) as total_charges
                FROM charter_charges
                GROUP BY charter_id
            ) cc ON c.charter_id = cc.charter_id
            WHERE (c.account_number = %s OR c.reserve_number = %s)
            AND c.charter_date::date BETWEEN %s::date - INTERVAL '7 days' 
                                         AND %s::date + INTERVAL '7 days'
            AND ABS(COALESCE(cc.total_charges, 0) - %s) < 50
            LIMIT 1
        """, (account, reserve, pay_date, pay_date, float(amount)))
        
        charter = cur.fetchone()
        if charter:
            potential_matches += 1
            if potential_matches <= 10:
                charter_id, charter_reserve, charter_account, charter_date, total_charges = charter
                print(f"  Payment {payment_id} ({pay_date}, ${amount:.2f}) → Charter {charter_id} (Reserve {charter_reserve}, {charter_date}, ${total_charges:.2f if total_charges else 0:.2f})")
    
    print()
    print(f"Found {potential_matches} potential matches in first 100 unmatched payments!")
    print()
    
    print("=" * 100)
    print("RECOMMENDATION:")
    print("=" * 100)
    print()
    print("The Cash Receipts Reports contain account numbers and reserve numbers that can help")
    print("match unmatched payments. We should:")
    print()
    print("1. Import Cash Receipts Report data (if available as structured data)")
    print("2. Match by: Account Number + Date (±7 days) + Amount (±$50 tolerance)")
    print("3. Create automated matching script for these patterns")
    print()
    
    if potential_matches > 0:
        print(f"[OK] At least {potential_matches} of 3,082 unmatched 2012 payments can likely be matched!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
