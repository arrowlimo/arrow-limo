import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*80)
print("CHECKING QB_ACCOUNTS TABLE")
print("="*80)

cur.execute("""
    SELECT qb_account_number, qb_name, qb_account_type, qb_description
    FROM qb_accounts 
    WHERE qb_account_number IN ('1000', '1010') 
       OR qb_name LIKE '%Scotia%' 
       OR qb_name LIKE '%CIBC%'
       OR qb_name LIKE '%1615%'
    ORDER BY qb_account_number
""")

rows = cur.fetchall()
if rows:
    for acct_num, name, acct_type, desc in rows:
        print(f"\nAccount: {acct_num}")
        print(f"  Name: {name}")
        print(f"  Type: {acct_type}")
        if desc:
            print(f"  Description: {desc}")
else:
    print("No matching accounts found in qb_accounts")

print("\n" + "="*80)
print("CHECKING CHART_OF_ACCOUNTS TABLE")
print("="*80)

cur.execute("""
    SELECT account_code, account_name, account_type, description
    FROM chart_of_accounts
    WHERE account_code IN ('1000', '1010')
       OR account_name LIKE '%Scotia%'
       OR account_name LIKE '%CIBC%'
    ORDER BY account_code
""")

rows = cur.fetchall()
if rows:
    for code, name, atype, notes in rows:
        print(f"\nAccount: {code}")
        print(f"  Name: {name}")
        print(f"  Type: {atype}")
        if notes:
            print(f"  Notes: {notes}")
else:
    print("No matching accounts found in chart_of_accounts")

cur.close()
conn.close()
