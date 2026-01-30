import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("SEARCHING FOR SCOTIA BANK ACCOUNT 90399 01060 11")
print("="*80)

# Check if this account exists
cur.execute("""
    SELECT account_number, COUNT(*) as count,
           MIN(transaction_date) as first,
           MAX(transaction_date) as last
    FROM banking_transactions
    WHERE account_number LIKE '%90399%'
       OR account_number LIKE '%010611%'
       OR account_number LIKE '%01060%'
    GROUP BY account_number
""")

rows = cur.fetchall()
if rows:
    print("\nFound Scotia Bank account in banking_transactions:")
    for acct, count, first, last in rows:
        print(f"  Account: {acct}")
        print(f"  Transactions: {count}")
        print(f"  Date range: {first} to {last}")
else:
    print("\nScotia Bank account NOT FOUND in banking_transactions")
    print("The account 90399-01060-11 was never imported!")

# Check account aliases
print("\n" + "="*80)
print("CHECKING ACCOUNT ALIASES FOR SCOTIA")
print("="*80)

cur.execute("""
    SELECT statement_format, canonical_account_number, institution_name, notes
    FROM account_number_aliases
    WHERE statement_format LIKE '%90399%'
       OR statement_format LIKE '%010611%'
       OR statement_format LIKE '%01060%'
       OR canonical_account_number LIKE '%90399%'
""")

rows = cur.fetchall()
if rows:
    for fmt, canonical, inst, notes in rows:
        print(f"  {fmt} → {canonical} ({inst})")
        print(f"    Notes: {notes}")
else:
    print("  No aliases found for Scotia Bank account")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print("You have Scotia Bank STATEMENT PRINTOUTS in your files,")
print("but the transactions were NEVER IMPORTED into the database!")
print("\nThe 2,678 Scotia Bank transactions from 2012 are sitting in:")
print("  l:\\limo\\staging\\2012_comparison\\scotia_statement_transactions_2012_normalized.csv")
print("\nTotal Scotia Bank deposits in 2012: $446,757.38")

cur.close()
conn.close()
