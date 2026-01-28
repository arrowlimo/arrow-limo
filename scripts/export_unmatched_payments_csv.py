#!/usr/bin/env python3
"""
Export all unmatched payments to CSV for manual review.
"""

import psycopg2
import csv
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
    
    print("Exporting unmatched payments to CSV...")
    
    # Export all unmatched payments
    cur.execute("""
        SELECT 
            p.payment_id,
            p.payment_date,
            COALESCE(p.account_number, '') as account_number,
            COALESCE(p.reserve_number, '') as reserve_number,
            COALESCE(p.payment_method, 'Unknown') as payment_method,
            COALESCE(p.amount, 0) as amount,
            COALESCE(p.check_number, '') as check_number,
            COALESCE(p.square_transaction_id, '') as square_transaction_id,
            COALESCE(p.notes, '') as notes,
            COALESCE(c.client_name, '') as client_name
        FROM payments p
        LEFT JOIN clients c ON p.account_number = c.client_id::text 
            OR p.account_number = LPAD(c.client_id::text, 5, '0')
        WHERE (p.charter_id IS NULL OR p.charter_id = 0)
        AND EXTRACT(YEAR FROM p.payment_date) BETWEEN 2007 AND 2024
        ORDER BY p.payment_date, p.payment_id
    """)
    
    rows = cur.fetchall()
    
    # Write to CSV
    output_file = r'L:\limo\unmatched_payments_for_review.csv'
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            'Payment ID',
            'Payment Date',
            'Account Number',
            'Reserve Number',
            'Payment Method',
            'Amount',
            'Check Number',
            'Square Transaction ID',
            'Notes',
            'Client Name'
        ])
        
        # Data
        for row in rows:
            payment_id, payment_date, account_num, reserve_num, method, amount, check_num, square_id, notes, client_name = row
            date_str = payment_date.strftime('%Y-%m-%d') if payment_date else ''
            writer.writerow([
                payment_id,
                date_str,
                account_num,
                reserve_num,
                method,
                f"{float(amount):.2f}",
                check_num,
                square_id,
                notes,
                client_name
            ])
    
    print(f"[OK] Exported {len(rows):,} unmatched payments to: {output_file}")
    print()
    
    # Summary by priority
    print("=" * 100)
    print("UNMATCHED PAYMENTS SUMMARY:")
    print("=" * 100)
    print()
    print(f"Total unmatched: {len(rows):,} payments")
    print()
    
    # Count by year
    year_counts = {}
    for row in rows:
        payment_date = row[1]
        if payment_date:
            year = payment_date.year
            year_counts[year] = year_counts.get(year, 0) + 1
    
    print("By Year:")
    for year in sorted(year_counts.keys()):
        count = year_counts[year]
        pct = 100 * count / len(rows)
        print(f"  {year}: {count:,} ({pct:.1f}%)")
    
    print()
    print("PRIORITY CATEGORIES:")
    print()
    
    # Payments with account numbers
    with_account = sum(1 for row in rows if row[2])
    print(f"1. With account number: {with_account:,} ({100*with_account/len(rows):.1f}%)")
    
    # Large amounts
    large = sum(1 for row in rows if float(row[5]) > 1000)
    print(f"2. Amount > $1,000: {large:,} ({100*large/len(rows):.1f}%)")
    
    # Recent (2020+)
    recent = sum(1 for row in rows if row[1] and row[1].year >= 2020)
    print(f"3. Year 2020+: {recent:,} ({100*recent/len(rows):.1f}%)")
    
    # 2012 peak
    year_2012 = sum(1 for row in rows if row[1] and row[1].year == 2012)
    print(f"4. Year 2012 (peak): {year_2012:,} ({100*year_2012/len(rows):.1f}%)")
    
    print()
    print("CSV file ready for manual review in Excel!")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
