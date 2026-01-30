#!/usr/bin/env python3
"""Check for cheques 215 and 216 in account 1615."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

print("=" * 100)
print("SEARCH FOR CHEQUES 215 & 216 IN ACCOUNT 1615")
print("=" * 100 + "\n")

# Check cheque_register for these cheques
for cheque_num in ['215', '216']:
    print(f"Cheque #{cheque_num}:")
    print("-" * 100)
    
    cur.execute("""
        SELECT id, account_number, cheque_number, cheque_date, payee, amount, 
               status, banking_transaction_id, memo
        FROM cheque_register
        WHERE cheque_number = %s
        ORDER BY account_number
    """, (cheque_num,))
    
    results = cur.fetchall()
    if results:
        for record_id, acct, chq, date, payee, amount, status, btid, memo in results:
            print(f"  Found in account {acct}")
            print(f"    ID: {record_id}")
            print(f"    Date: {date}")
            print(f"    Payee: {payee}")
            print(f"    Amount: ${amount:,.2f}")
            print(f"    Status: {status}")
            print(f"    Banking TX ID: {btid}")
            print(f"    Memo: {memo}")
    else:
        print(f"  NOT found in cheque_register")
    print()

# Check if there are any banking transactions that mention these cheques
print("\n" + "=" * 100)
print("BANKING TRANSACTIONS MENTIONING CHEQUES 215 & 216")
print("=" * 100 + "\n")

for cheque_num in ['215', '216']:
    cur.execute("""
        SELECT transaction_id, account_number, transaction_date, description, 
               debit_amount, credit_amount
        FROM banking_transactions
        WHERE (description LIKE %s OR check_number = %s)
        ORDER BY account_number
    """, (f'%{cheque_num}%', cheque_num))
    
    results = cur.fetchall()
    print(f"Cheque #{cheque_num}:")
    if results:
        for tid, acct, date, desc, debit, credit in results:
            amount = debit or credit
            print(f"  TX {tid} | Account {acct} | {date} | ${amount:,.2f}")
            print(f"    {desc}")
    else:
        print(f"  No banking transactions found")
    print()

cur.close()
conn.close()

print("✅ Analysis complete")
