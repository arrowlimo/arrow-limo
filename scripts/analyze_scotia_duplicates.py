#!/usr/bin/env python
"""
Analyze Scotia 2012 duplicates in database.
Verified statement has 70 transactions; database has 816—11.6x bloated.
"""
import psycopg2
from collections import defaultdict, Counter
from datetime import datetime
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_duplicates():
    conn = get_db_connection()
    cur = conn.cursor()

    # Get all Scotia 2012 transactions
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id
    """)
    
    transactions = cur.fetchall()
    print(f"Total 2012 Scotia transactions in database: {len(transactions)}")
    print()

    # Find exact duplicates (same date, description, amount)
    print("=" * 100)
    print("EXACT DUPLICATES (same date, description, debit/credit)")
    print("=" * 100)
    
    composite_key = defaultdict(list)
    for txn_id, txn_date, desc, debit, credit, balance in transactions:
        key = (txn_date, desc, debit, credit)
        composite_key[key].append((txn_id, balance))
    
    exact_duplicates = {k: v for k, v in composite_key.items() if len(v) > 1}
    
    if exact_duplicates:
        for (txn_date, desc, debit, credit), txn_list in sorted(exact_duplicates.items()):
            print(f"\n  {txn_date} | {desc[:50]:50s} | DR:{debit:9.2f} | CR:{credit:9.2f}")
            for txn_id, balance in txn_list:
                print(f"    └─ ID {txn_id:5d}: Balance ${balance:12.2f}")
    
    total_dup_records = sum(len(v) - 1 for v in exact_duplicates.values())
    print(f"\nTotal exact duplicate records: {total_dup_records}")
    
    # Find date/amount matches with description variations
    print("\n" + "=" * 100)
    print("DATE/AMOUNT DUPLICATES (same date & amount, description varies)")
    print("=" * 100)
    
    date_amount_key = defaultdict(list)
    for txn_id, txn_date, desc, debit, credit, balance in transactions:
        key = (txn_date, debit, credit)
        date_amount_key[key].append((txn_id, desc, balance))
    
    date_amount_dups = {k: v for k, v in date_amount_key.items() if len(v) > 1}
    
    if date_amount_dups:
        for (txn_date, debit, credit), txn_list in sorted(date_amount_dups.items())[:20]:  # Show first 20
            print(f"\n  {txn_date} | DR:{debit:9.2f} | CR:{credit:9.2f}")
            for txn_id, desc, balance in txn_list:
                print(f"    └─ ID {txn_id:5d}: {desc[:60]:60s} Balance ${balance:12.2f}")
    
    total_date_amt_records = sum(len(v) - 1 for v in date_amount_dups.values())
    print(f"\nTotal date/amount duplicate records: {total_date_amt_records}")
    
    # Find description pattern duplicates (credit memos split?)
    print("\n" + "=" * 100)
    print("CREDIT MEMO ANALYSIS (VISA/MC/IDP batch deposits)")
    print("=" * 100)
    
    credit_memos = [t for t in transactions if 'CREDIT MEMO' in t[2].upper()]
    print(f"\nTotal CREDIT MEMO transactions: {len(credit_memos)}")
    
    # Group by date
    by_date = defaultdict(list)
    for txn_id, txn_date, desc, debit, credit, balance in credit_memos:
        by_date[txn_date].append((txn_id, desc, credit))
    
    multi_credit_dates = {k: v for k, v in by_date.items() if len(v) > 1}
    
    if multi_credit_dates:
        print(f"\nDates with multiple credit memos: {len(multi_credit_dates)}")
        for txn_date in sorted(multi_credit_dates.keys())[:10]:
            memos = multi_credit_dates[txn_date]
            total = sum(cr for _, _, cr in memos)
            print(f"\n  {txn_date}: {len(memos)} memos, total credit ${total:9.2f}")
            for txn_id, desc, credit in memos:
                print(f"    └─ ID {txn_id:5d}: {desc[:60]:60s} ${credit:9.2f}")
    
    # Statistics
    print("\n" + "=" * 100)
    print("SUMMARY STATISTICS")
    print("=" * 100)
    print(f"Total transactions in database: {len(transactions)}")
    print(f"Exact duplicate records (same everything): {total_dup_records}")
    print(f"Date/amount duplicate records (varies descriptions): {total_date_amt_records}")
    print(f"Credit memo transactions: {len(credit_memos)}")
    print(f"Dates with multiple credit memos: {len(multi_credit_dates)}")
    print(f"\nEstimated duplicate rate: {(total_dup_records + total_date_amt_records) / len(transactions) * 100:.1f}%")
    
    # Show top descriptions by frequency
    print("\n" + "=" * 100)
    print("TOP 20 DESCRIPTIONS BY FREQUENCY")
    print("=" * 100)
    
    desc_freq = Counter(t[2] for t in transactions)
    for desc, count in desc_freq.most_common(20):
        if count > 1:
            print(f"  {count:3d}x  {desc[:70]:70s}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_duplicates()
