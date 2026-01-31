#!/usr/bin/env python3
"""Check for account 8362 receipts and duplicates."""
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*70)
print("ACCOUNT 8362 ANALYSIS")
print("="*70)

# Banking transactions for 8362
cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '8362'")
bt_8362 = cur.fetchone()[0]
print(f"\nBanking transactions for account 8362: {bt_8362:,}")

# Receipts linked to 8362
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id) 
    FROM receipts r
    JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.account_number = '8362'
""")
r_8362 = cur.fetchone()[0]
print(f"Receipts linked to account 8362: {r_8362:,}")

if bt_8362 > 0:
    # Date range
    cur.execute("""
        SELECT MIN(transaction_date), MAX(transaction_date), COUNT(*) 
        FROM banking_transactions 
        WHERE account_number = '8362'
    """)
    min_date, max_date, count = cur.fetchone()
    print(f"\nDate range: {min_date} to {max_date}")
    print(f"Total transactions: {count:,}")
    
    # Check if these were in the years we deleted
    cur.execute("""
        SELECT 
            EXTRACT(YEAR FROM transaction_date) as year,
            COUNT(*) as count
        FROM banking_transactions
        WHERE account_number = '8362'
        GROUP BY year
        ORDER BY year
    """)
    
    print("\nTransactions by year:")
    for row in cur.fetchall():
        year = int(row[0]) if row[0] else 0
        count = row[1]
        status = "DELETED" if 2012 <= year <= 2017 else "KEPT"
        print(f"  {year}: {count:,} ({status})")
    
    # Sample transactions
    print("\nSample 8362 transactions:")
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE account_number = '8362'
        ORDER BY transaction_date
        LIMIT 10
    """)
    
    print(f"\n{'Date':<12} {'Description':<40} {'Debit':>12} {'Credit':>12}")
    print("-" * 80)
    for row in cur.fetchall():
        date, desc, debit, credit = row
        desc_str = (desc or '')[:38]
        debit_str = f"${debit:,.2f}" if debit else ""
        credit_str = f"${credit:,.2f}" if credit else ""
        print(f"{date} {desc_str:<40} {debit_str:>12} {credit_str:>12}")
    
else:
    print("\n✅ NO account 8362 transactions found!")
    print("   Either they were all in 2012-2017 (deleted) or never existed")
    print("   The 8362 duplication issue has been resolved!")

cur.close()
conn.close()
