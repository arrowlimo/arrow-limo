#!/usr/bin/env python
"""Check for existing Cash Box / Petty Cash accounts"""

import psycopg2

conn = psycopg2.connect('host=localhost user=postgres password=***REDACTED*** dbname=almsdata')
cur = conn.cursor()

print("="*80)
print("CHECKING FOR EXISTING CASH BOX / PETTY CASH ACCOUNTS")
print("="*80)

# Search banking_transactions for cash-related entries
cur.execute("""
SELECT DISTINCT description 
FROM banking_transactions 
WHERE description ILIKE '%cash%' OR description ILIKE '%float%' OR description ILIKE '%petty%'
ORDER BY description
LIMIT 20
""")

cash_entries = cur.fetchall()
print(f"\n1. Banking transactions with 'cash/float/petty':")
if cash_entries:
    for row in cash_entries:
        print(f"   • {row[0]}")
else:
    print("   (none found)")

# Check mapped_bank_accounts
print(f"\n2. All mapped bank accounts:")
cur.execute("SELECT mapped_bank_account_id, account_name, account_number, bank_name FROM mapped_bank_accounts ORDER BY mapped_bank_account_id")
for row in cur.fetchall():
    bank_id, acct_name, acct_num, bank_name = row
    print(f"   ID {bank_id}: {acct_name} ({acct_num}) - {bank_name}")

# Check GL accounts for cash-related codes
print(f"\n3. Chart of accounts with 'cash' or 'float':")
cur.execute("""
SELECT account_code, account_name 
FROM chart_of_accounts 
WHERE account_name ILIKE '%cash%' OR account_name ILIKE '%float%' OR account_name ILIKE '%petty%'
ORDER BY account_code
""")
cash_accounts = cur.fetchall()
if cash_accounts:
    for code, name in cash_accounts:
        print(f"   {code}: {name}")
else:
    print("   (none found)")

# Check what GL accounts exist
print(f"\n4. All GL accounts (Asset/Liability/Cash-like):")
cur.execute("""
SELECT account_code, account_name 
FROM chart_of_accounts 
WHERE account_code LIKE '1%' OR account_code LIKE '2%'
ORDER BY account_code
""")
asset_accounts = cur.fetchall()
if asset_accounts:
    for code, name in asset_accounts[:15]:
        print(f"   {code}: {name}")
else:
    print("   (none found)")

cur.close()
conn.close()
print("\n" + "="*80)
