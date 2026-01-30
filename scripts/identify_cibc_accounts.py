#!/usr/bin/env python3
"""
Which CIBC account has the 2012 data?
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("CIBC ACCOUNTS IN DATABASE")
print("="*80)

cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as total,
        COUNT(CASE WHEN EXTRACT(YEAR FROM transaction_date) = 2012 THEN 1 END) as count_2012,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date
    FROM banking_transactions
    WHERE account_number IN ('0228362', '1615', '00339 74-61615')
    GROUP BY account_number
    ORDER BY count_2012 DESC
""")

print(f"\n{'Account':<20} {'Total':<10} {'2012':<10} {'First Date':<15} {'Last Date':<15}")
print("-" * 80)

for row in cur.fetchall():
    print(f"{row[0]:<20} {row[1]:<10} {row[2]:<10} {str(row[3]):<15} {str(row[4]):<15}")

# Check what "1615" refers to in the database
print("\n" + "="*80)
print("ACCOUNT DETAILS")
print("="*80)

for account in ['0228362', '1615']:
    print(f"\nAccount {account}:")
    
    cur.execute("""
        SELECT DISTINCT source_file 
        FROM banking_transactions
        WHERE account_number = %s
        LIMIT 5
    """, (account,))
    
    sources = [row[0] for row in cur.fetchall() if row[0]]
    if sources:
        print(f"  Source files: {sources[:3]}")
    
    # Get a sample transaction
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = %s
          AND EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date
        LIMIT 1
    """, (account,))
    
    sample = cur.fetchone()
    if sample:
        print(f"  Sample 2012 transaction: {sample[0]} | {sample[1]}")

cur.close()
conn.close()
