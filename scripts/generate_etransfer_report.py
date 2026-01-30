#!/usr/bin/env python3
"""
Generate comprehensive e-transfer report organized by IN/OUT with matching analysis.

Report includes:
1. Summary stats (IN vs OUT)
2. Exact date+amount matches
3. Name extraction and matching to drivers/clients
4. Unmatched transactions requiring review

Usage:
    python generate_etransfer_report.py > etransfer_report.txt
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

def print_section(title):
    print("\n" + "="*100)
    print(title.center(100))
    print("="*100)

def main():
    conn = get_conn()
    cur = conn.cursor()
    
    print_section("E-TRANSFER DATA ANALYSIS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. SUMMARY STATISTICS
    print_section("1. SUMMARY STATISTICS")
    
    cur.execute("""
        SELECT 
            direction,
            COUNT(*) as count,
            SUM(amount) as total_amount,
            MIN(amount) as min_amount,
            MAX(amount) as max_amount,
            AVG(amount) as avg_amount,
            MIN(transaction_date) as earliest,
            MAX(transaction_date) as latest
        FROM etransfer_transactions
        GROUP BY direction
        ORDER BY direction
    """)
    
    print(f"\n{'Direction':<10} | {'Count':>8} | {'Total Amount':>15} | {'Min':>12} | {'Max':>12} | {'Avg':>12} | {'Date Range'}")
    print("-" * 100)
    
    for row in cur.fetchall():
        direction, count, total, min_amt, max_amt, avg_amt, earliest, latest = row
        print(f"{direction:<10} | {count:>8,} | ${total:>14,.2f} | ${min_amt:>11,.2f} | ${max_amt:>11,.2f} | ${avg_amt:>11,.2f} | {earliest} to {latest}")
    
    # 2. MATCHING STATISTICS
    print_section("2. MATCHING STATISTICS")
    
    cur.execute("""
        SELECT 
            match_confidence,
            COUNT(*) as count,
            SUM(amount) as total
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NOT NULL
        GROUP BY match_confidence
        ORDER BY 
            CASE match_confidence
                WHEN 'exact' THEN 1
                WHEN 'date_amount' THEN 2
                WHEN 'amount_only' THEN 3
                ELSE 4
            END
    """)
    
    print(f"\n{'Match Type':<20} | {'Count':>8} | {'Total Amount':>15}")
    print("-" * 50)
    
    for conf, count, total in cur.fetchall():
        print(f"{conf:<20} | {count:>8,} | ${total:>14,.2f}")
    
    cur.execute("""
        SELECT COUNT(*), SUM(amount)
        FROM etransfer_transactions
        WHERE banking_transaction_id IS NULL
    """)
    
    unmatched = cur.fetchone()
    print(f"{'Unmatched':<20} | {unmatched[0]:>8,} | ${unmatched[1] or 0:>14,.2f}")
    
    # 3. INCOMING E-TRANSFERS (Exact Date+Amount Matches)
    print_section("3. INCOMING E-TRANSFERS - Exact Date+Amount Matches (Top 50)")
    
    cur.execute("""
        SELECT 
            et.transaction_date,
            et.amount,
            et.sender_recipient_name,
            et.match_confidence,
            bt.description as banking_desc
        FROM etransfer_transactions et
        LEFT JOIN banking_transactions bt ON et.banking_transaction_id = bt.transaction_id
        WHERE et.direction = 'IN'
        AND et.match_confidence = 'date_amount'
        ORDER BY et.amount DESC
        LIMIT 50
    """)
    
    print(f"\n{'Date':<12} | {'Amount':>12} | {'Name from Email':<30} | {'Banking Description':<50}")
    print("-" * 100)
    
    for row in cur.fetchall():
        tdate, amt, name, conf, desc = row
        print(f"{str(tdate):<12} | ${amt:>11,.2f} | {(name or 'Unknown')[:30]:<30} | {(desc or '')[:50]}")
    
    # 4. OUTGOING E-TRANSFERS (Exact Date+Amount Matches)
    print_section("4. OUTGOING E-TRANSFERS - Exact Date+Amount Matches (Top 50)")
    
    cur.execute("""
        SELECT 
            et.transaction_date,
            et.amount,
            et.sender_recipient_name,
            et.match_confidence,
            bt.description as banking_desc
        FROM etransfer_transactions et
        LEFT JOIN banking_transactions bt ON et.banking_transaction_id = bt.transaction_id
        WHERE et.direction = 'OUT'
        AND et.match_confidence = 'date_amount'
        ORDER BY et.amount DESC
        LIMIT 50
    """)
    
    print(f"\n{'Date':<12} | {'Amount':>12} | {'Name from Email':<30} | {'Banking Description':<50}")
    print("-" * 100)
    
    for row in cur.fetchall():
        tdate, amt, name, conf, desc = row
        print(f"{str(tdate):<12} | ${amt:>11,.2f} | {(name or 'Unknown')[:30]:<30} | {(desc or '')[:50]}")
    
    # 5. HIGH-VALUE UNMATCHED INCOMING
    print_section("5. UNMATCHED INCOMING E-TRANSFERS >$1,000 (Top 30)")
    
    cur.execute("""
        SELECT 
            et.transaction_date,
            et.amount,
            et.sender_recipient_name,
            et.sender_recipient_email,
            et.reference_number
        FROM etransfer_transactions et
        WHERE et.direction = 'IN'
        AND et.banking_transaction_id IS NULL
        AND et.amount >= 1000
        ORDER BY et.amount DESC
        LIMIT 30
    """)
    
    print(f"\n{'Date':<12} | {'Amount':>12} | {'Name':<30} | {'Email':<30} | {'Ref#'}")
    print("-" * 100)
    
    for row in cur.fetchall():
        tdate, amt, name, email, ref = row
        print(f"{str(tdate):<12} | ${amt:>11,.2f} | {(name or 'Unknown')[:30]:<30} | {(email or '')[:30]:<30} | {ref or ''}")
    
    # 6. HIGH-VALUE UNMATCHED OUTGOING
    print_section("6. UNMATCHED OUTGOING E-TRANSFERS >$1,000 (Top 30)")
    
    cur.execute("""
        SELECT 
            et.transaction_date,
            et.amount,
            et.sender_recipient_name,
            et.sender_recipient_email,
            et.reference_number
        FROM etransfer_transactions et
        WHERE et.direction = 'OUT'
        AND et.banking_transaction_id IS NULL
        AND et.amount >= 1000
        ORDER BY et.amount DESC
        LIMIT 30
    """)
    
    print(f"\n{'Date':<12} | {'Amount':>12} | {'Name':<30} | {'Email':<30} | {'Ref#'}")
    print("-" * 100)
    
    for row in cur.fetchall():
        tdate, amt, name, email, ref = row
        print(f"{str(tdate):<12} | ${amt:>11,.2f} | {(name or 'Unknown')[:30]:<30} | {(email or '')[:30]:<30} | {ref or ''}")
    
    # 7. BANKING DESCRIPTIONS WITH NAMES (for matched transfers)
    print_section("7. MATCHED TRANSFERS WITH IDENTIFIABLE NAMES IN BANKING (Sample 30)")
    
    cur.execute("""
        SELECT 
            et.direction,
            et.transaction_date,
            et.amount,
            bt.description
        FROM etransfer_transactions et
        JOIN banking_transactions bt ON et.banking_transaction_id = bt.transaction_id
        WHERE bt.description ILIKE '%e-transfer%#%'
        OR bt.description ~ '[A-Z][a-z]+ [A-Z][a-z]+'
        ORDER BY et.amount DESC
        LIMIT 30
    """)
    
    print(f"\n{'Dir':<4} | {'Date':<12} | {'Amount':>12} | {'Banking Description'}")
    print("-" * 100)
    
    for row in cur.fetchall():
        direction, tdate, amt, desc = row
        print(f"{direction:<4} | {str(tdate):<12} | ${amt:>11,.2f} | {desc}")
    
    # 8. YEARLY BREAKDOWN
    print_section("8. YEARLY BREAKDOWN")
    
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            direction,
            COUNT(*) as count,
            SUM(amount) as total
        FROM etransfer_transactions
        GROUP BY EXTRACT(YEAR FROM transaction_date), direction
        ORDER BY year, direction
    """)
    
    print(f"\n{'Year':<6} | {'Direction':<10} | {'Count':>8} | {'Total Amount':>15}")
    print("-" * 50)
    
    for year, direction, count, total in cur.fetchall():
        print(f"{int(year):<6} | {direction:<10} | {count:>8,} | ${total:>14,.2f}")
    
    conn.close()
    
    print("\n" + "="*100)
    print("END OF REPORT")
    print("="*100)

if __name__ == '__main__':
    main()
