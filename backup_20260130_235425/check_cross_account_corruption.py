#!/usr/bin/env python3
"""Check for corruption pattern: Scotia/other account transactions recorded as CIBC 8362."""

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
print("CROSS-ACCOUNT CORRUPTION CHECK - CIBC Account 0228362")
print("=" * 100 + "\n")

# Look for patterns that suggest transactions belong to Scotia (account 2)
# Scotia account number format, typical Scotia vendor names, etc.

print("SUSPICIOUS PATTERNS IN CIBC 0228362:\n")

# Pattern 1: Look for vendor descriptions that mention Scotia/other bank
print("1. Transactions mentioning Scotia or other banks:")
print("-" * 100)

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description ILIKE '%scotia%' 
         OR description ILIKE '%bmo%'
         OR description ILIKE '%royal%'
         OR description ILIKE '%td bank%'
         OR description ILIKE '%rbc%')
    LIMIT 20
""")

results = cur.fetchall()
if results:
    for trans_id, date, desc, debit, credit in results:
        amount = debit or credit
        print(f"  {trans_id} | {date} | ${amount:,.2f} | {desc}")
else:
    print("  None found\n")

# Pattern 2: Look for Scotia account numbers in CIBC data
print("\n2. Scotia account number references in CIBC:")
print("-" * 100)

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND (description LIKE '%903990106011%'
         OR description LIKE '%90399%'
         OR description LIKE '%061006011%')
    LIMIT 20
""")

results = cur.fetchall()
if results:
    for trans_id, date, desc, debit, credit in results:
        amount = debit or credit
        print(f"  {trans_id} | {date} | ${amount:,.2f} | {desc}")
else:
    print("  None found\n")

# Pattern 3: Look for transactions that don't fit CIBC pattern
# (Missing cheque numbers, odd descriptions, inconsistent formatting)
print("\n3. Transactions with unusual/missing check numbers or odd descriptions:")
print("-" * 100)

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, check_number
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    AND (
        (debit_amount > 100000)  -- Unusually large
        OR (description LIKE '%deposit%' AND credit_amount > 50000)
        OR (description LIKE '%journal%' AND COALESCE(debit_amount, 0) > 0)
    )
    ORDER BY COALESCE(debit_amount, 0) DESC
    LIMIT 20
""")

results = cur.fetchall()
if results:
    for trans_id, date, desc, debit, credit, check_num in results:
        amount = debit or credit
        print(f"  {trans_id} | {date} | ${amount:,.2f}")
        print(f"         {desc}")
        print(f"         Check: {check_num}")
else:
    print("  None found (after deletion of 2 suspicious checks)\n")

# Pattern 4: Check account balances - do they make sense?
print("\n4. Account balance trends (first transaction of each month in 2012):")
print("-" * 100)

cur.execute("""
    SELECT DISTINCT ON (date_trunc('month', transaction_date))
           transaction_date, balance
    FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY date_trunc('month', transaction_date), transaction_date
""")

results = cur.fetchall()
if results:
    for date, balance in results:
        month = date.strftime('%Y-%m')
        print(f"  {month}: ${float(balance):12,.2f}")
else:
    print("  No data\n")

print("\n" + "=" * 100)
print("CROSS-ACCOUNT ANALYSIS")
print("=" * 100 + "\n")

# Compare transactions across accounts
print("Summary of all accounts in 2012:\n")

cur.execute("""
    SELECT account_number, COUNT(*) as tx_count, 
           SUM(COALESCE(debit_amount, 0) + COALESCE(credit_amount, 0)) as volume
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY account_number
    ORDER BY account_number
""")

for acct, count, volume in cur.fetchall():
    print(f"  Account {acct}: {count:5d} transactions, ${float(volume):12,.2f} volume")

cur.close()
conn.close()

print("\n✅ Analysis complete")
