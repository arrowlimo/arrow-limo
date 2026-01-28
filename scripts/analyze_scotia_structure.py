#!/usr/bin/env python
"""
Deep dive: Compare verified statement structure to database.
Why does database have 2,318 records when statement has only 70?
"""
import psycopg2
from datetime import datetime
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Verified statement transactions (from user)
VERIFIED = """
2012-01-01	Opening balance						40
2012-01-03	CENTEX PETRO...						60
2012-01-09	ESSO...							90
2012-01-13	CENTEX...						110
2012-01-31	SERVICE CHARGE						100
2012-02-03	SHELL...						140
2012-02-15	DOMO GAS...						160
2012-02-22	TRANSFER IN						200
2012-02-22	TRANSFER OUT						140
2012-02-23	PAYMENT						91
2012-02-29	DEPOSIT 						100
... (pattern)
2012-07-12	END MONTH CLOSE						3214.39
"""

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def analyze_structure():
    conn = get_db_connection()
    cur = conn.cursor()

    print("=" * 100)
    print("SCOTIA 2012 COMPREHENSIVE ANALYSIS")
    print("=" * 100)

    # Get full 2012 data
    cur.execute("""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            credit_amount,
            balance,
            source_hash
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id
    """)
    
    all_txns = cur.fetchall()
    print(f"\nTotal 2012 records in database: {len(all_txns)}")
    
    # Unique source_hash?
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(DISTINCT source_hash) as unique_hashes,
            COUNT(*) FILTER (WHERE source_hash IS NULL) as null_hashes
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    total, unique_hashes, null_hashes = cur.fetchone()
    print(f"Unique source_hash values: {unique_hashes}")
    print(f"NULL source_hash values: {null_hashes}")
    print(f"Dedup ratio: {unique_hashes / total if total > 0 else 0:.1%}")
    
    # Check for imported source markers
    print("\n" + "=" * 100)
    print("TRANSACTION SOURCES")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            COUNT(*) as cnt,
            CASE 
                WHEN description LIKE '%staging%' THEN 'staging'
                WHEN description LIKE '%CSV%' THEN 'CSV'
                WHEN description LIKE '%QuickBooks%' THEN 'QuickBooks'
                WHEN description LIKE '%manual%' THEN 'manual'
                WHEN description LIKE '%PDF%' THEN 'PDF'
                ELSE 'unknown'
            END as source
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY source
        ORDER BY cnt DESC
    """)
    
    for cnt, source in cur.fetchall():
        print(f"  {cnt:5d} records: {source}")
    
    # Sample specific transactions
    print("\n" + "=" * 100)
    print("SAMPLE: First 20 transactions of 2012")
    print("=" * 100)
    
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
        LIMIT 20
    """)
    
    for txn_id, txn_date, desc, debit, credit, balance in cur.fetchall():
        print(f"  {txn_id:5d} | {txn_date} | {desc[:50]:50s} | DR:{debit:9.2f} CR:{credit:9.2f} | Bal: ${balance:12.2f}")
    
    # Check if multiple imports of same data exist
    print("\n" + "=" * 100)
    print("DUPLICATE PATTERN ANALYSIS")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            description,
            transaction_date,
            COUNT(*) as cnt,
            SUM(debit_amount) as total_debit,
            SUM(credit_amount) as total_credit,
            ARRAY_AGG(DISTINCT ROUND(balance::numeric, 2)) as balance_values
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY description, transaction_date
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 30
    """)
    
    print("\nTop 30 (date, description) groups with duplicates:")
    for desc, txn_date, cnt, total_debit, total_credit, balances in cur.fetchall():
        print(f"  {cnt}x | {txn_date} | {desc[:50]:50s}")
        print(f"       Total: DR ${total_debit:10.2f} | CR ${total_credit:10.2f} | Balances: {balances}")
    
    # Monthly breakdown
    print("\n" + "=" * 100)
    print("MONTHLY BREAKDOWN")
    print("=" * 100)
    
    cur.execute("""
        SELECT 
            EXTRACT(MONTH FROM transaction_date)::int as month,
            COUNT(*) as txn_count,
            SUM(debit_amount) as month_debits,
            SUM(credit_amount) as month_credits,
            (ARRAY_AGG(balance ORDER BY transaction_date DESC LIMIT 1))[1] as ending_balance
        FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
        GROUP BY EXTRACT(MONTH FROM transaction_date)
        ORDER BY month
    """)
    
    for month, txn_count, debits, credits, ending_bal in cur.fetchall():
        print(f"  Month {month:2d}: {txn_count:4d} txns | DR: ${debits:12.2f} | CR: ${credits:12.2f} | Ending: ${ending_bal:12.2f}")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_structure()
