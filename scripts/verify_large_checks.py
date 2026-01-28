#!/usr/bin/env python3
"""Verify the large check transactions - check account context."""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("VERIFY LARGE CHECK TRANSACTIONS")
print("=" * 100 + "\n")

# Oct 2012 context - around transaction 60389
print("OCTOBER 2012 - Around Check #955.46 (Oct 31, 2012)")
print("-" * 100)
print("\nAll transactions Oct 2012, sorted by amount DESC:\n")

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           COALESCE(debit_amount, 0) - COALESCE(credit_amount, 0) as net_debit, balance
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND EXTRACT(MONTH FROM transaction_date) = 10
    ORDER BY COALESCE(debit_amount, 0) DESC
    LIMIT 20
""")

for trans_id, date, desc, debit, credit, net, balance in cur.fetchall():
    amount = debit or credit
    print(f"ID {trans_id:5d} | {date} | ${amount:12,.2f} | Bal: ${balance:12,.2f}")
    print(f"         {desc}")
    if trans_id == 60389:
        print("         ^^^ CHEQUE 955.46 ^^^")
    print()

# Jul 2012 context - around transaction 60330
print("\n" + "=" * 100)
print("JULY 2012 - Around Check WO -120.00 (Jul 13, 2012)")
print("-" * 100)
print("\nAll transactions Jul 2012, sorted by amount DESC:\n")

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, 
           COALESCE(debit_amount, 0) - COALESCE(credit_amount, 0) as net_debit, balance
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    AND EXTRACT(MONTH FROM transaction_date) = 7
    ORDER BY COALESCE(debit_amount, 0) DESC
    LIMIT 20
""")

for trans_id, date, desc, debit, credit, net, balance in cur.fetchall():
    amount = debit or credit
    print(f"ID {trans_id:5d} | {date} | ${amount:12,.2f} | Bal: ${balance:12,.2f}")
    print(f"         {desc}")
    if trans_id == 60330:
        print("         ^^^ CHEQUE WO -120.00 ^^^")
    print()

# Check account summary for 2012
print("\n" + "=" * 100)
print("2012 ACCOUNT SUMMARY")
print("-" * 100 + "\n")

cur.execute("""
    SELECT COUNT(*) as tx_count, 
           SUM(COALESCE(debit_amount, 0)) as total_debits,
           SUM(COALESCE(credit_amount, 0)) as total_credits,
           MIN(balance) as min_balance,
           MAX(balance) as max_balance
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
""")

tx_count, debits, credits, min_bal, max_bal = cur.fetchone()
print(f"Total transactions: {tx_count}")
print(f"Total debits: ${float(debits):,.2f}")
print(f"Total credits: ${float(credits):,.2f}")
print(f"Min balance: ${float(min_bal):,.2f}")
print(f"Max balance: ${float(max_bal):,.2f}")

# Check if these amounts make sense contextually
print("\n" + "=" * 100)
print("ASSESSMENT")
print("=" * 100)

cur.execute("SELECT debit_amount FROM banking_transactions WHERE transaction_id = 60389")
amount_389 = cur.fetchone()[0]

cur.execute("SELECT debit_amount FROM banking_transactions WHERE transaction_id = 60330")
amount_330 = cur.fetchone()[0]

print(f"\nThe large checks:")
print(f"  Transaction 60389: ${float(amount_389):,.2f}")
print(f"  Transaction 60330: ${float(amount_330):,.2f}")
print(f"  Combined: ${float(amount_389 + amount_330):,.2f}")

if float(amount_389) > 150000 or float(amount_330) > 150000:
    print("\n⚠️  These are extremely large transactions.")
    print("Possible explanations:")
    print("  1. Payroll for the entire year")
    print("  2. Loan payment or financing")
    print("  3. Large vendor payment (fleet purchase, etc.)")
    print("  4. Data entry error or duplicate")
    print("  5. Account transfer or sweep")

cur.close()
conn.close()

print("\n✅ Analysis complete")
