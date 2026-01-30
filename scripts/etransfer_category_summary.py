#!/usr/bin/env python3
"""
Generate categorized e-transfer summary report.
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'almsdata')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', '***REDACTED***')

def get_conn():
    return psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)

def main():
    conn = get_conn()
    cur = conn.cursor()
    
    print("\n" + "="*100)
    print("E-TRANSFER CATEGORIZED SUMMARY REPORT")
    print("="*100)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Overall summary
    cur.execute("""
        SELECT 
            category,
            category_description,
            COUNT(*) as count,
            SUM(amount) as total,
            COUNT(CASE WHEN direction = 'IN' THEN 1 END) as incoming_count,
            SUM(CASE WHEN direction = 'IN' THEN amount ELSE 0 END) as incoming_total,
            COUNT(CASE WHEN direction = 'OUT' THEN 1 END) as outgoing_count,
            SUM(CASE WHEN direction = 'OUT' THEN amount ELSE 0 END) as outgoing_total
        FROM etransfer_transactions
        WHERE category IS NOT NULL
        GROUP BY category, category_description
        ORDER BY total DESC
    """)
    
    print("\n" + "="*100)
    print("SUMMARY BY CATEGORY")
    print("="*100)
    print(f"\n{'Category':<30} | {'Total':>15} | {'IN':>8} | {'IN $':>12} | {'OUT':>8} | {'OUT $':>12}")
    print("-" * 100)
    
    categories = cur.fetchall()
    grand_total = 0
    
    for cat, desc, count, total, in_count, in_total, out_count, out_total in categories:
        print(f"{desc[:30]:<30} | ${total:>14,.2f} | {in_count:>8,} | ${in_total:>11,.2f} | {out_count:>8,} | ${out_total:>11,.2f}")
        grand_total += total
    
    print("-" * 100)
    print(f"{'TOTAL CATEGORIZED':<30} | ${grand_total:>14,.2f}")
    
    # Uncategorized
    cur.execute("""
        SELECT 
            COUNT(*),
            SUM(amount)
        FROM etransfer_transactions
        WHERE category IS NULL
        AND banking_transaction_id IS NOT NULL
    """)
    
    uncat = cur.fetchone()
    if uncat[0]:
        print(f"{'Uncategorized (matched)':<30} | ${uncat[1] or 0:>14,.2f} | {uncat[0]:,} transactions")
    
    # Unmatched to banking
    cur.execute("""
        SELECT 
            COUNT(*),
            SUM(amount)
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NULL
    """)
    
    unmatched = cur.fetchone()
    if unmatched[0]:
        print(f"{'Not matched to banking':<30} | ${unmatched[1] or 0:>14,.2f} | {unmatched[0]:,} transactions")
    
    # Yearly breakdown by category
    print("\n" + "="*100)
    print("YEARLY BREAKDOWN BY CATEGORY")
    print("="*100)
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            category_description,
            COUNT(*) as count,
            SUM(amount) as total
        FROM etransfer_transactions
        WHERE category IS NOT NULL
        GROUP BY EXTRACT(YEAR FROM transaction_date), category_description
        ORDER BY year, total DESC
    """)
    
    current_year = None
    for year, desc, count, total in cur.fetchall():
        if year != current_year:
            if current_year is not None:
                print()
            print(f"\n{int(year)}:")
            print("-" * 80)
            current_year = year
        
        print(f"  {desc[:45]:<45} | {count:>6,} | ${total:>12,.2f}")
    
    # Net position analysis
    print("\n" + "="*100)
    print("NET POSITION BY CATEGORY (IN - OUT)")
    print("="*100)
    
    cur.execute("""
        SELECT 
            category_description,
            SUM(CASE WHEN direction = 'IN' THEN amount ELSE 0 END) as incoming,
            SUM(CASE WHEN direction = 'OUT' THEN amount ELSE 0 END) as outgoing,
            SUM(CASE WHEN direction = 'IN' THEN amount ELSE -amount END) as net
        FROM etransfer_transactions
        WHERE category IS NOT NULL
        GROUP BY category_description
        ORDER BY net DESC
    """)
    
    print(f"\n{'Category':<45} | {'Incoming':>15} | {'Outgoing':>15} | {'Net':>15}")
    print("-" * 100)
    
    for desc, incoming, outgoing, net in cur.fetchall():
        print(f"{desc[:45]:<45} | ${incoming:>14,.2f} | ${outgoing:>14,.2f} | ${net:>14,.2f}")
    
    conn.close()
    
    print("\n" + "="*100)
    print("END OF REPORT")
    print("="*100)

if __name__ == '__main__':
    main()
