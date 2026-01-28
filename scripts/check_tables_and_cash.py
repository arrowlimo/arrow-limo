#!/usr/bin/env python
"""Check database tables and Cash Box setup"""

import psycopg2

conn = psycopg2.connect('host=localhost user=postgres password=***REMOVED*** dbname=almsdata')
cur = conn.cursor()

print("="*80)
print("DATABASE TABLE CHECK")
print("="*80)

# List all tables
cur.execute("""
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name
""")

tables = [r[0] for r in cur.fetchall()]
print(f"\nAll tables ({len(tables)}):")
for t in sorted(tables):
    print(f"  • {t}")

# Check banking_transactions for account info
print("\n" + "="*80)
print("CASH/FLOAT REFERENCES IN SYSTEM")
print("="*80)

cur.execute("""
SELECT DISTINCT description 
FROM banking_transactions 
WHERE description ILIKE '%cash%' OR description ILIKE '%float%' OR description ILIKE '%petty%'
ORDER BY description
LIMIT 15
""")

cash_entries = cur.fetchall()
print(f"\nCash-related banking entries:")
if cash_entries:
    for row in cash_entries:
        print(f"  • {row[0]}")

# Check if any banking_transactions are marked as "CASH BOX" type
print(f"\nChecking banking_transactions account info:")
cur.execute("""
SELECT DISTINCT 
    transaction_id, transaction_date, description, 
    debit_amount, credit_amount, category, mapped_bank_account_id
FROM banking_transactions 
WHERE description ILIKE '%cash%' OR category ILIKE '%cash%'
LIMIT 5
""")

rows = cur.fetchall()
if rows:
    print(f"Found {len(rows)} cash-related banking transactions:")
    for row in rows:
        trans_id, date, desc, debit, credit, cat, bank_acct = row
        print(f"  ID {trans_id}: {desc[:50]} | Bank Acct: {bank_acct}")

# Check if mapped_bank_account_id column exists in banking_transactions
print(f"\nColumns in banking_transactions:")
cur.execute("""
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'banking_transactions'
ORDER BY ordinal_position
LIMIT 20
""")

for col, dtype in cur.fetchall():
    print(f"  • {col}: {dtype}")

# Check chart_of_accounts
print(f"\nGeraldine's Cash GL accounts:")
cur.execute("""
SELECT account_code, account_name 
FROM chart_of_accounts 
WHERE account_name ILIKE '%cash%' 
   OR account_name ILIKE '%float%' 
   OR account_name ILIKE '%petty%'
   OR account_code IN ('1010', '1020', '1030', '1040', '1050')
ORDER BY account_code
""")

gl_rows = cur.fetchall()
if gl_rows:
    for code, name in gl_rows:
        print(f"  {code}: {name}")

cur.close()
conn.close()

print("\n" + "="*80)
