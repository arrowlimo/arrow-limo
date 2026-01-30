#!/usr/bin/env python3
"""
Count unmatched payments and provide detailed breakdown for manual review.
"""

import psycopg2
from datetime import datetime

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="almsdata",
        user="postgres",
        password="***REDACTED***"
    )

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("=" * 100)
    print("UNMATCHED PAYMENTS ANALYSIS - FOR MANUAL REVIEW")
    print("=" * 100)
    print()
    
    # Total unmatched payments
    cur.execute("""
        SELECT 
            COUNT(*) as total_unmatched,
            SUM(COALESCE(amount, 0)) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
    """)
    
    total_count, total_amount = cur.fetchone()
    
    print(f"TOTAL UNMATCHED PAYMENTS (2007-2024): {total_count:,}")
    print(f"TOTAL AMOUNT: ${float(total_amount):,.2f}")
    print()
    
    # Breakdown by year
    print("=" * 100)
    print("UNMATCHED PAYMENTS BY YEAR:")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM payment_date) as year,
            COUNT(*) as count,
            SUM(COALESCE(amount, 0)) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY EXTRACT(YEAR FROM payment_date)
        ORDER BY year
    """)
    
    year_totals = []
    for row in cur.fetchall():
        year, count, amount = row
        year_totals.append((int(year), count, float(amount)))
        print(f"  {int(year)}: {count:,} payments (${float(amount):,.2f})")
    
    # Breakdown by payment method
    print()
    print("=" * 100)
    print("UNMATCHED PAYMENTS BY METHOD:")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            COALESCE(payment_method, 'Unknown') as method,
            COUNT(*) as count,
            SUM(COALESCE(amount, 0)) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY payment_method
        ORDER BY count DESC
    """)
    
    for row in cur.fetchall():
        method, count, amount = row
        print(f"  {method}: {count:,} payments (${float(amount):,.2f})")
    
    # Breakdown by amount ranges
    print()
    print("=" * 100)
    print("UNMATCHED PAYMENTS BY AMOUNT RANGE:")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            CASE 
                WHEN amount < 100 THEN 'Under $100'
                WHEN amount < 250 THEN '$100-$250'
                WHEN amount < 500 THEN '$250-$500'
                WHEN amount < 1000 THEN '$500-$1,000'
                WHEN amount < 2500 THEN '$1,000-$2,500'
                ELSE 'Over $2,500'
            END as amount_range,
            COUNT(*) as count,
            SUM(COALESCE(amount, 0)) as total_amount
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        GROUP BY 
            CASE 
                WHEN amount < 100 THEN 'Under $100'
                WHEN amount < 250 THEN '$100-$250'
                WHEN amount < 500 THEN '$250-$500'
                WHEN amount < 1000 THEN '$500-$1,000'
                WHEN amount < 2500 THEN '$1,000-$2,500'
                ELSE 'Over $2,500'
            END
        ORDER BY MIN(amount)
    """)
    
    for row in cur.fetchall():
        range_name, count, amount = row
        print(f"  {range_name}: {count:,} payments (${float(amount):,.2f})")
    
    # Sample list for manual review
    print()
    print("=" * 100)
    print("FIRST 50 UNMATCHED PAYMENTS FOR MANUAL REVIEW:")
    print("=" * 100)
    print()
    
    cur.execute("""
        SELECT 
            payment_id,
            payment_date,
            COALESCE(account_number, '') as account_number,
            COALESCE(reserve_number, '') as reserve_number,
            COALESCE(payment_method, 'Unknown') as payment_method,
            COALESCE(amount, 0) as amount,
            COALESCE(notes, '') as notes
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
        ORDER BY payment_date, payment_id
        LIMIT 50
    """)
    
    print(f"{'ID':<8} {'Date':<12} {'Account':<10} {'Reserve':<10} {'Method':<15} {'Amount':<12} {'Notes':<40}")
    print("-" * 120)
    
    for row in cur.fetchall():
        payment_id, payment_date, account_num, reserve_num, method, amount, notes = row
        date_str = payment_date.strftime('%Y-%m-%d') if payment_date else 'N/A'
        notes_short = (notes[:37] + '...') if len(notes) > 40 else notes
        print(f"{payment_id:<8} {date_str:<12} {account_num:<10} {reserve_num:<10} {method:<15} ${float(amount):<11,.2f} {notes_short:<40}")
    
    print()
    print(f"... (showing first 50 of {total_count:,} unmatched payments)")
    print()
    
    # Priority recommendations
    print("=" * 100)
    print("MANUAL REVIEW RECOMMENDATIONS:")
    print("=" * 100)
    print()
    
    # Find payments with reserve numbers
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND reserve_number IS NOT NULL
        AND reserve_number != ''
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
    """)
    
    with_reserve = cur.fetchone()[0]
    
    print(f"1. HIGH PRIORITY - Payments with reserve numbers: {with_reserve:,}")
    print(f"   These have explicit reserve numbers and should be easy to match")
    print()
    
    # Find payments with account numbers
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND account_number IS NOT NULL
        AND account_number != ''
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
    """)
    
    with_account = cur.fetchone()[0]
    
    print(f"2. MEDIUM PRIORITY - Payments with account numbers: {with_account:,}")
    print(f"   Can match to client account, then find charters by date/amount")
    print()
    
    # Large amounts
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND amount > 1000
        AND EXTRACT(YEAR FROM payment_date) BETWEEN 2007 AND 2024
    """)
    
    large_amounts = cur.fetchone()[0]
    
    print(f"3. FINANCIAL PRIORITY - Large payments (>$1,000): {large_amounts:,}")
    print(f"   High-value payments should be matched for financial accuracy")
    print()
    
    # Recent payments
    cur.execute("""
        SELECT COUNT(*)
        FROM payments
        WHERE (charter_id IS NULL OR charter_id = 0)
        AND EXTRACT(YEAR FROM payment_date) >= 2020
    """)
    
    recent = cur.fetchone()[0]
    
    print(f"4. TIME PRIORITY - Recent payments (2020+): {recent:,}")
    print(f"   More recent payments easier to verify and correct")
    print()
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
