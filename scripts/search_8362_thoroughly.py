#!/usr/bin/env python3
"""Search for 8362 in all banking data fields."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*70)
print("SEARCHING FOR 8362 IN BANKING DATA")
print("="*70)

# Check all account numbers containing 8362
print("\n1. Account numbers containing '8362':")
cur.execute("""
    SELECT DISTINCT account_number, COUNT(*) 
    FROM banking_transactions 
    WHERE account_number LIKE '%8362%'
    GROUP BY account_number
    ORDER BY COUNT(*) DESC
""")
results = cur.fetchall()
if results:
    for acct, count in results:
        print(f"   {acct}: {count:,} transactions")
else:
    print("   None found")

# Check source files containing 8362
print("\n2. Source files containing '8362':")
cur.execute("""
    SELECT DISTINCT source_file, COUNT(*) 
    FROM banking_transactions 
    WHERE source_file LIKE '%8362%'
    GROUP BY source_file
    ORDER BY COUNT(*) DESC
""")
results = cur.fetchall()
if results:
    for src, count in results:
        print(f"   {src}: {count:,} transactions")
        
    # Get details for the first one
    print("\n3. Details for CIBC 8362 transactions:")
    cur.execute("""
        SELECT 
            bt.source_file,
            MIN(bt.transaction_date) as min_date,
            MAX(bt.transaction_date) as max_date,
            COUNT(*) as trans_count,
            COUNT(DISTINCT r.receipt_id) as receipt_count
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.source_file LIKE '%8362%'
        GROUP BY bt.source_file
    """)
    
    for row in cur.fetchall():
        src, min_date, max_date, trans_count, receipt_count = row
        print(f"\n   Source: {src}")
        print(f"   Date range: {min_date} to {max_date}")
        print(f"   Transactions: {trans_count:,}")
        print(f"   Receipts created: {receipt_count:,}")
    
    # Year breakdown
    print("\n4. CIBC 8362 transactions by year:")
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM bt.transaction_date) as year,
            COUNT(*) as trans_count,
            COUNT(DISTINCT r.receipt_id) as receipt_count
        FROM banking_transactions bt
        LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
        WHERE bt.source_file LIKE '%8362%'
        GROUP BY year
        ORDER BY year
    """)
    
    print(f"\n   {'Year':<10} {'Transactions':>15} {'Receipts':>15} {'Status'}")
    print("   " + "-" * 60)
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else 0
        trans = row[1]
        receipts = row[2]
        status = "DELETED" if 2012 <= year <= 2017 else "KEPT"
        print(f"   {year:<10} {trans:>15,} {receipts:>15,} {status}")
    
else:
    print("   None found")

# Check bank_id patterns
print("\n5. Banking transactions by bank_id (for reference):")
cur.execute("""
    SELECT 
        bank_id,
        account_number,
        COUNT(*) as count
    FROM banking_transactions
    WHERE bank_id IS NOT NULL
    GROUP BY bank_id, account_number
    ORDER BY bank_id, count DESC
""")

current_bank = None
for row in cur.fetchall():
    bank_id, acct, count = row
    if bank_id != current_bank:
        print(f"\n   bank_id {bank_id}:")
        current_bank = bank_id
    acct_str = acct if acct else "NULL"
    print(f"     {acct_str}: {count:,} transactions")

cur.close()
conn.close()
