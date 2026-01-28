#!/usr/bin/env python3
"""
Analyze charter-payment matching status.
Focus on non-zero balance charters and unmatched payments (excluding 2025-2026).
"""

import psycopg2

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
    print("CHARTER-PAYMENT MATCHING ANALYSIS (2007-2024)")
    print("=" * 100)
    print()
    
    # Get payment matching status (excluding 2025-2026)
    print("PAYMENT MATCHING STATUS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_payments,
            COUNT(charter_id) as matched_payments,
            COUNT(*) - COUNT(charter_id) as unmatched_payments,
            SUM(amount) as total_amount,
            SUM(CASE WHEN charter_id IS NOT NULL THEN amount ELSE 0 END) as matched_amount,
            SUM(CASE WHEN charter_id IS NULL THEN amount ELSE 0 END) as unmatched_amount
        FROM payments
        WHERE EXTRACT(YEAR FROM payment_date) < 2025
    """)
    
    row = cur.fetchone()
    total_pmts, matched_pmts, unmatched_pmts, total_amt, matched_amt, unmatched_amt = row
    
    match_rate = 100 * matched_pmts / total_pmts if total_pmts > 0 else 0
    
    print(f"Total payments (2007-2024): {total_pmts:,}")
    print(f"Matched to charters: {matched_pmts:,} ({match_rate:.1f}%)")
    print(f"Unmatched payments: {unmatched_pmts:,} ({100-match_rate:.1f}%)")
    print(f"\nTotal payment amount: ${total_amt:,.2f}")
    print(f"Matched amount: ${matched_amt:,.2f}")
    print(f"Unmatched amount: ${unmatched_amt:,.2f}")
    
    # Payment breakdown by year
    print("\n" + "=" * 100)
    print("UNMATCHED PAYMENTS BY YEAR:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as unmatched_count,
            SUM(amount) as unmatched_amount
        FROM payments
        WHERE reserve_number IS NULL
            AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year
    """)
    
    print(f"{'Year':<6} {'Unmatched Payments':>18} {'Unmatched Amount':>20}")
    print("-" * 100)
    for year, count, amount in cur.fetchall():
        print(f"{int(year):<6} {count:>18,} ${amount:>18,.2f}")
    
    # Charter balance status (excluding 2025-2026)
    print("\n" + "=" * 100)
    print("CHARTER BALANCE ANALYSIS (2007-2024):")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as total_charters,
            COUNT(CASE WHEN balance > 0 THEN 1 END) as charters_with_balance,
            COUNT(CASE WHEN balance = 0 THEN 1 END) as charters_paid_off,
            SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END) as total_outstanding
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) < 2025
    """)
    
    row = cur.fetchone()
    total_charters, with_balance, paid_off, outstanding = row
    
    balance_rate = 100 * with_balance / total_charters if total_charters > 0 else 0
    
    print(f"Total charters (2007-2024): {total_charters:,}")
    print(f"Charters with balance > 0: {with_balance:,} ({balance_rate:.1f}%)")
    print(f"Charters paid off (balance = 0): {paid_off:,} ({100-balance_rate:.1f}%)")
    print(f"Total outstanding balance: ${outstanding:,.2f}")
    
    # Charter balance by year
    print("\n" + "=" * 100)
    print("CHARTERS WITH NON-ZERO BALANCE BY YEAR:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM charter_date) as year,
            COUNT(*) as total_charters,
            COUNT(CASE WHEN balance > 0 THEN 1 END) as with_balance,
            SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END) as outstanding_balance
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) BETWEEN 2007 AND 2024
        GROUP BY EXTRACT(YEAR FROM charter_date)
        ORDER BY year
    """)
    
    print(f"{'Year':<6} {'Total Charters':>15} {'With Balance':>15} {'Outstanding':>20}")
    print("-" * 100)
    total_with_balance = 0
    total_outstanding = 0
    for year, total, with_bal, outstanding in cur.fetchall():
        print(f"{int(year):<6} {total:>15,} {with_bal:>15,} ${outstanding:>18,.2f}")
        total_with_balance += with_bal
        total_outstanding += outstanding
    print("-" * 100)
    print(f"{'TOTAL':<6} {'':<15} {total_with_balance:>15,} ${total_outstanding:>18,.2f}")
    
    # Top outstanding balances
    print("\n" + "=" * 100)
    print("TOP 20 CHARTERS WITH OUTSTANDING BALANCE (2007-2024):")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            charter_id,
            reserve_number,
            charter_date,
            client_id,
            balance,
            total_amount_due
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) < 2025
            AND balance > 0
        ORDER BY balance DESC
        LIMIT 20
    """)
    
    print(f"{'Charter ID':<12} {'Reserve #':<10} {'Date':<12} {'Client ID':<10} {'Balance':>15} {'Total Due':>15}")
    print("-" * 100)
    for charter_id, reserve, date, client_id, balance, total_due in cur.fetchall():
        reserve_str = str(reserve) if reserve else 'N/A'
        client_str = str(client_id) if client_id else 'N/A'
        total_str = f"${total_due:,.2f}" if total_due else 'N/A'
        print(f"{charter_id:<12} {reserve_str:<10} {str(date):<12} {client_str:<10} ${balance:>13,.2f} {total_str:>15}")
    
    # Summary statistics
    print("\n" + "=" * 100)
    print("SUMMARY STATISTICS:")
    print("-" * 100)
    
    cur.execute("""
        SELECT 
            AVG(balance) as avg_balance,
            MIN(balance) as min_balance,
            MAX(balance) as max_balance,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY balance) as median_balance
        FROM charters
        WHERE EXTRACT(YEAR FROM charter_date) < 2025
            AND balance > 0
    """)
    
    row = cur.fetchone()
    avg_bal, min_bal, max_bal, median_bal = row
    
    print(f"Average outstanding balance: ${avg_bal:,.2f}")
    print(f"Median outstanding balance: ${median_bal:,.2f}")
    print(f"Minimum outstanding balance: ${min_bal:,.2f}")
    print(f"Maximum outstanding balance: ${max_bal:,.2f}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
