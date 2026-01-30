#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Find duplicate transactions in 2014 CIBC data.

Duplicates can occur when:
- Same PDF page was processed twice
- Same transaction appears on multiple statement pages
- OCR/parsing created duplicate entries
"""

import psycopg2
from collections import defaultdict

def get_conn():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def main():
    print("Find 2014 CIBC Duplicate Transactions")
    print("=" * 70)
    
    conn = get_conn()
    cur = conn.cursor()
    
    # Find duplicates by (date, description, debit_amount, credit_amount)
    cur.execute("""
        SELECT 
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            COUNT(*) as dup_count,
            ARRAY_AGG(transaction_id ORDER BY transaction_id) as ids
        FROM banking_transactions
        WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2014
        GROUP BY transaction_date, description, debit_amount, credit_amount
        HAVING COUNT(*) > 1
        ORDER BY transaction_date, COUNT(*) DESC
    """)
    
    duplicates = cur.fetchall()
    
    if not duplicates:
        print("✓ No duplicates found")
        conn.close()
        return
    
    print(f"Found {len(duplicates)} duplicate groups")
    
    # Group by month
    by_month = defaultdict(list)
    for row in duplicates:
        month = row[0].strftime('%Y-%m')
        by_month[month].append(row)
    
    total_dup_transactions = 0
    
    for month in sorted(by_month.keys()):
        dups = by_month[month]
        month_dups = sum(dup[4] - 1 for dup in dups)  # Count extras only
        total_dup_transactions += month_dups
        
        print(f"\n{month}: {len(dups)} duplicate groups, {month_dups} extra transactions")
        
        for date, desc, debit, credit, count, ids in dups[:5]:
            print(f"  {date} {desc[:50]:50s} D:{debit:>8.2f} C:{credit:>8.2f} x{count}")
            print(f"    IDs: {ids}")
        
        if len(dups) > 5:
            print(f"  ... and {len(dups) - 5} more duplicate groups")
    
    print(f"\n{'=' * 70}")
    print(f"Total duplicate groups: {len(duplicates)}")
    print(f"Total extra transactions to remove: {total_dup_transactions}")
    print(f"\nCurrent 2014 transaction count: {sum(dup[4] for dup in duplicates) + len(duplicates)}")
    print(f"After deduplication: {len(duplicates) + sum(1 for dup in duplicates)}")
    
    conn.close()

if __name__ == '__main__':
    main()
