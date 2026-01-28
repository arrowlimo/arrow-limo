#!/usr/bin/env python3
"""
Deep dive into 1010 Scotia Bank Main vs CIBC accounts
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata', 
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("\n" + "="*80)
print("INVESTIGATING: Is 1010 really CIBC or is it Scotia Bank?")
print("="*80)

# Check unified_general_ledger for 1010 entries
print("\n1010 SCOTIA BANK MAIN - Sample transactions from unified_general_ledger:")
print("-"*80)
cur.execute("""
    SELECT 
        transaction_date,
        account_code,
        account_name,
        description,
        debit_amount,
        credit_amount,
        source_system,
        source_transaction_id
    FROM unified_general_ledger
    WHERE account_code = '1010'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
    LIMIT 10
""")

for row in cur.fetchall():
    date, code, name, desc, debit, credit, source, src_id = row
    print(f"{date} | {code} {name} | {desc[:40]:40} | D:{debit or 0:.2f} C:{credit or 0:.2f} | {source}")

# Check 1000 entries
print("\n" + "="*80)
print("1000 CIBC BANK 1615 - Sample transactions from unified_general_ledger:")
print("-"*80)
cur.execute("""
    SELECT 
        transaction_date,
        account_code,
        account_name,
        description,
        debit_amount,
        credit_amount,
        source_system,
        source_transaction_id
    FROM unified_general_ledger
    WHERE account_code = '1000'
      AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date
    LIMIT 10
""")

for row in cur.fetchall():
    date, code, name, desc, debit, credit, source, src_id = row
    print(f"{date} | {code} {name} | {desc[:40]:40} | D:{debit or 0:.2f} C:{credit or 0:.2f} | {source}")

# Check if there are any Scotia Bank references in banking_transactions
print("\n" + "="*80)
print("SEARCHING FOR SCOTIA BANK IN BANKING TRANSACTIONS:")
print("-"*80)
cur.execute("""
    SELECT DISTINCT account_number, COUNT(*) 
    FROM banking_transactions 
    WHERE LOWER(description) LIKE '%scotia%'
       OR account_number LIKE '%scot%'
    GROUP BY account_number
""")

scotia_refs = cur.fetchall()
if scotia_refs:
    for acct, count in scotia_refs:
        print(f"Account {acct}: {count} transactions mentioning Scotia")
else:
    print("No Scotia Bank references found in banking_transactions")

# Check all distinct accounts in 2012
print("\n" + "="*80)
print("ALL BANKING ACCOUNTS IN 2012 WITH INSTITUTION INFO:")
print("-"*80)
cur.execute("""
    SELECT DISTINCT 
        bt.account_number,
        COALESCE(aa.institution_name, 'Unknown') as institution,
        COALESCE(aa.account_type, 'Unknown') as type,
        COUNT(*) as txn_count
    FROM banking_transactions bt
    LEFT JOIN account_number_aliases aa ON bt.account_number = aa.canonical_account_number
    WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
    GROUP BY bt.account_number, aa.institution_name, aa.account_type
    ORDER BY bt.account_number
""")

for acct, inst, atype, count in cur.fetchall():
    print(f"{acct:20} | {inst:15} | {atype:15} | {count:5} transactions")

# Check the account_number_aliases for 1010
print("\n" + "="*80)
print("ACCOUNT ALIAS FOR '1010':")
print("-"*80)
cur.execute("""
    SELECT * FROM account_number_aliases WHERE statement_format = '1010'
""")

alias_row = cur.fetchone()
if alias_row:
    print(f"Statement format: 1010")
    print(f"Maps to: {alias_row[2]}")
    print(f"Institution: {alias_row[3]}")
    print(f"Type: {alias_row[4]}")
    print(f"Notes: {alias_row[5]}")
    print(f"\nCONCLUSION: This alias mapping appears to be INCORRECT!")
    print("The name 'Scotia Bank Main' is likely a QuickBooks labeling error.")
else:
    print("No alias found for 1010")

cur.close()
conn.close()

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
print("The '1010 Scotia Bank Main' in QuickBooks appears to be a mislabeling.")
print("It should probably refer to CIBC 0228362 (the main checking account).")
print("OR there may be a separate Scotia Bank account that needs to be identified.")
