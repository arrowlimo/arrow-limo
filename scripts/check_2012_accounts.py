#!/usr/bin/env python3
"""
Check all banking accounts in 2012 and their relationship to QuickBooks accounts
"""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata', 
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("\n" + "="*80)
print("2012 BANKING ACCOUNTS")
print("="*80)

# Get all accounts used in 2012
cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(COALESCE(debit_amount, 0)) as total_debits,
        SUM(COALESCE(credit_amount, 0)) as total_credits
    FROM banking_transactions 
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012 
    GROUP BY account_number 
    ORDER BY account_number
""")

for row in cur.fetchall():
    acct, count, first, last, debits, credits = row
    print(f"\nAccount: {acct}")
    print(f"  Transactions: {count:,}")
    print(f"  Date range: {first} to {last}")
    print(f"  Total debits: ${debits:,.2f}")
    print(f"  Total credits: ${credits:,.2f}")

# Check account aliases/mappings
print("\n" + "="*80)
print("ACCOUNT NUMBER ALIASES (Statement Format Mappings)")
print("="*80)

cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'account_number_aliases'
""")
alias_columns = [r[0] for r in cur.fetchall()]
print(f"Available columns: {', '.join(alias_columns)}")

if alias_columns:
    cur.execute("""
        SELECT *
        FROM account_number_aliases
        ORDER BY statement_format
    """)
else:
    cur.execute("SELECT 1 WHERE FALSE")

rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"  {row}")
else:
    print("No account aliases defined")

# Check if there's QuickBooks account mapping
print("\n" + "="*80)
print("CHECKING QUICKBOOKS ACCOUNT REFERENCES IN 2012")
print("="*80)

cur.execute("""
    SELECT DISTINCT 
        account_code,
        account_name,
        COUNT(*) as entries
    FROM unified_general_ledger
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
      AND (account_code LIKE '1000%' OR account_code LIKE '1010%')
    GROUP BY account_code, account_name
    ORDER BY account_code
""")

qb_accounts = cur.fetchall()
if qb_accounts:
    for code, name, entries in qb_accounts:
        print(f"{code}: {name} ({entries:,} entries)")
else:
    print("No QuickBooks 1000/1010 accounts found in unified_general_ledger")

# Check journal entries
cur.execute("""
    SELECT DISTINCT 
        "Account",
        "Description",
        COUNT(*) as entries
    FROM journal
    WHERE EXTRACT(YEAR FROM "EntryDate") = 2012
      AND ("Account" LIKE '1000%' OR "Account" LIKE '1010%')
    GROUP BY "Account", "Description"
    ORDER BY "Account"
    LIMIT 20
""")

journal_accounts = cur.fetchall()
if journal_accounts:
    print("\n" + "="*80)
    print("JOURNAL ENTRIES WITH 1000/1010 ACCOUNTS IN 2012")
    print("="*80)
    for acct, desc, entries in journal_accounts:
        print(f"{acct}: {desc[:60]} ({entries:,} entries)")

cur.close()
conn.close()
