#!/usr/bin/env python3
"""
Find the transactions shown in the PDF screenshot (Apr 16-20, 2012)
Account: 74-61615 (CIBC)
"""

import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# The account number could be stored as 0228362 or some other format
account_numbers = ['0228362', '74-61615', '00339 74-61615', '7461615']

print("="*80)
print("SEARCHING FOR APRIL 16-20, 2012 TRANSACTIONS")
print("="*80)

# Key transactions to find from the PDF:
# Apr 16: RENT/LEASE UMI136 - $1,985.65
# Apr 16: CHEQUE 1730202 248 - $3,000.00
# Apr 17: CREDIT MEMO 4017775 VISA - $495.50
# Apr 18: PURCHASE#000001038066 - $36.56
# Apr 19: CHEQUE 1730704 261 - $2,191.47
# Apr 19: CENTRA CEERIGHO - $88.33
# Apr 20: MISC PAYMENT - $256.35

for account in account_numbers:
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date BETWEEN '2012-04-16' AND '2012-04-20'
        ORDER BY transaction_date, transaction_id
    """, (account,))
    
    rows = cur.fetchall()
    
    if rows:
        print(f"\n✅ Found transactions for account {account}")
        print(f"\n{'Date':<12} {'Description':<50} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
        print("-" * 105)
        
        for row in rows:
            debit = f"${row[2]:,.2f}" if row[2] else ""
            credit = f"${row[3]:,.2f}" if row[3] else ""
            balance = f"${row[4]:,.2f}" if row[4] else ""
            print(f"{str(row[0]):<12} {row[1]:<50} {debit:>12} {credit:>12} {balance:>12}")
        
        print(f"\nTotal: {len(rows)} transactions")

# If not found, check what we have for April 2012
print("\n" + "="*80)
print("ALL APRIL 2012 TRANSACTIONS IN DATABASE (for account 0228362)")
print("="*80)

cur.execute("""
    SELECT COUNT(*),
           MIN(transaction_date),
           MAX(transaction_date)
    FROM banking_transactions
    WHERE account_number = '0228362'
      AND transaction_date BETWEEN '2012-04-01' AND '2012-04-30'
""")

count, first, last = cur.fetchone()
print(f"\nTotal April 2012 transactions: {count}")
print(f"Date range: {first} to {last}")

if count > 0:
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount, balance
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND transaction_date BETWEEN '2012-04-01' AND '2012-04-30'
        ORDER BY transaction_date, transaction_id
    """)
    
    rows = cur.fetchall()
    print(f"\n{'Date':<12} {'Description':<50} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
    print("-" * 105)
    
    for row in rows:
        debit = f"${row[2]:,.2f}" if row[2] else ""
        credit = f"${row[3]:,.2f}" if row[3] else ""
        balance = f"${row[4]:,.2f}" if row[4] else ""
        print(f"{str(row[0]):<12} {row[1]:<50} {debit:>12} {credit:>12} {balance:>12}")

# Check if specific key transactions exist anywhere
print("\n" + "="*80)
print("SEARCHING FOR KEY TRANSACTIONS BY DESCRIPTION")
print("="*80)

key_searches = [
    ("RENT/LEASE UMI136", 1985.65),
    ("CHEQUE 1730202", 3000.00),
    ("CHEQUE 1730704", 2191.47),
    ("CENTRA CEERIGHO", 88.33),
    ("GEORGE'S PIZZA", 28.93),
]

for desc, amount in key_searches:
    cur.execute("""
        SELECT transaction_date, description, debit_amount, credit_amount
        FROM banking_transactions
        WHERE description ILIKE %s
          AND (debit_amount = %s OR credit_amount = %s)
        LIMIT 5
    """, (f"%{desc}%", amount, amount))
    
    results = cur.fetchall()
    if results:
        print(f"\n✅ Found: {desc} (${amount})")
        for r in results:
            print(f"   {r[0]} | {r[1]} | Debit: {r[2]} | Credit: {r[3]}")
    else:
        print(f"\n❌ NOT FOUND: {desc} (${amount})")

cur.close()
conn.close()
