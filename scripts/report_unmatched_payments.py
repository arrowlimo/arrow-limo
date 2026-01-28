#!/usr/bin/env python3
"""
Report all unmatched payments with detailed breakdown.
Generates comprehensive analysis of payments without charter links.
"""

import psycopg2
import os
from decimal import Decimal
from datetime import datetime

def get_db_connection():
    """Get database connection using environment variables."""
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
    print("UNMATCHED PAYMENTS ANALYSIS - Arrow Limousine")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)
    
    # Summary by payment method
    print("\n### SUMMARY BY PAYMENT METHOD (2007-2024) ###\n")
    cur.execute("""
        SELECT 
            COALESCE(payment_method, '(None)') as method,
            COUNT(*) as count,
            COALESCE(SUM(amount), 0) as total_amount,
            MIN(payment_date) as earliest,
            MAX(payment_date) as latest
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        GROUP BY payment_method
        ORDER BY total_amount DESC
    """)
    
    summary = cur.fetchall()
    print(f"{'Payment Method':<20} {'Count':<10} {'Total Amount':<15} {'Date Range':<30}")
    print("-" * 80)
    
    grand_total = Decimal(0)
    grand_count = 0
    for method, count, amount, earliest, latest in summary:
        print(f"{method:<20} {count:<10} ${amount:>12,.2f}  {earliest} to {latest}")
        grand_total += amount
        grand_count += count
    
    print("-" * 80)
    print(f"{'TOTAL':<20} {grand_count:<10} ${grand_total:>12,.2f}")
    
    # Top 50 unmatched by amount
    print("\n\n### TOP 50 UNMATCHED PAYMENTS BY AMOUNT ###\n")
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            reserve_number,
            account_number,
            amount,
            payment_method,
            reference_number,
            COALESCE(square_customer_name, '') as customer_name,
            COALESCE(notes, '') as notes
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        ORDER BY amount DESC
        LIMIT 50
    """)
    
    top50 = cur.fetchall()
    print(f"{'ID':<8} {'Date':<12} {'Reserve':<10} {'Account':<10} {'Amount':<12} {'Method':<15} {'Customer':<30}")
    print("-" * 110)
    
    for row in top50:
        pid, pdate, resnum, acctnum, amt, method, refnum, cust, notes = row
        cust_str = cust[:27] + '...' if len(cust) > 30 else cust
        # Handle None values properly
        resnum_str = str(resnum) if resnum else ''
        acctnum_str = str(acctnum) if acctnum else ''
        method_str = str(method) if method else ''
        amt_val = float(amt) if amt is not None else 0.0
        print(f"{pid:<8} {str(pdate):<12} {resnum_str:<10} {acctnum_str:<10} ${amt_val:>9.2f}  {method_str:<15} {cust_str:<30}")
    
    # Breakdown by year and method
    print("\n\n### YEARLY BREAKDOWN BY PAYMENT METHOD ###\n")
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COALESCE(payment_method, '(None)') as method,
            COUNT(*) as count,
            COALESCE(SUM(amount), 0) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        GROUP BY EXTRACT(YEAR FROM payment_date), payment_method
        ORDER BY year DESC, total_amount DESC
    """)
    
    yearly = cur.fetchall()
    current_year = None
    for year, method, count, amount in yearly:
        if year != current_year:
            if current_year is not None:
                print()
            print(f"\n{int(year)}:")
            print(f"  {'Method':<20} {'Count':<10} {'Amount':<15}")
            print(f"  {'-'*50}")
            current_year = year
        print(f"  {method:<20} {count:<10} ${amount:>12,.2f}")
    
    # Specific patterns
    print("\n\n### PAYMENT PATTERNS ANALYSIS ###\n")
    
    # Payments with reserve numbers but no charter link
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND reserve_number IS NOT NULL
        AND reserve_number != ''
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
    """)
    res_count, res_amount = cur.fetchone()
    print(f"Has reserve_number but no charter link: {res_count} payments, ${res_amount:,.2f}")
    
    # Payments with account number but no charter link
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND account_number IS NOT NULL
        AND account_number != ''
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
    """)
    acct_count, acct_amount = cur.fetchone()
    print(f"Has account_number but no charter link: {acct_count} payments, ${acct_amount:,.2f}")
    
    # No identifiers at all
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND (reserve_number IS NULL OR reserve_number = '')
        AND (account_number IS NULL OR account_number = '')
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
    """)
    no_id_count, no_id_amount = cur.fetchone()
    print(f"No identifiers (no reserve/account): {no_id_count} payments, ${no_id_amount:,.2f}")
    
    # Negative amounts (refunds)
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(amount), 0)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND amount < 0
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
    """)
    neg_count, neg_amount = cur.fetchone()
    print(f"Negative amounts (refunds/reversals): {neg_count} payments, ${neg_amount:,.2f}")
    
    # Sample of reserve numbers without match
    print("\n\n### SAMPLE RESERVE NUMBERS WITHOUT CHARTER MATCH (First 20) ###\n")
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            reserve_number,
            amount,
            payment_method
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND reserve_number IS NOT NULL
        AND reserve_number != ''
        AND payment_date >= '2007-01-01'
        AND payment_date < '2025-01-01'
        ORDER BY payment_date DESC, amount DESC
        LIMIT 20
    """)
    
    samples = cur.fetchall()
    print(f"{'ID':<8} {'Date':<12} {'Reserve Number':<15} {'Amount':<12} {'Method':<20}")
    print("-" * 80)
    for pid, pdate, resnum, amt, method in samples:
        resnum_str = str(resnum) if resnum else ''
        method_str = str(method) if method else ''
        amt_val = float(amt) if amt is not None else 0.0
        print(f"{pid:<8} {str(pdate):<12} {resnum_str:<15} ${amt_val:>9.2f}  {method_str:<20}")
    
    print("\n" + "=" * 100)
    print(f"SUMMARY: {grand_count} total unmatched payments, ${grand_total:,.2f} unmatched value")
    print("=" * 100)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
