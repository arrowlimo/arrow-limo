import psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

# Look for account 1010 in any QuickBooks-related data
print("Looking for tables with account code data...")
cur.execute("""
    SELECT table_name 
    FROM information_schema.columns 
    WHERE column_name LIKE '%account%' 
      AND table_schema = 'public'
      AND table_name NOT LIKE 'pg_%'
    GROUP BY table_name
    ORDER BY table_name
""")
print("Tables with account columns:")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\n" + "="*80)
print("Checking if 1010 is actually a SEPARATE Scotia Bank account...")
print("="*80)

# Check the 3648117 account - maybe it's Scotia?
cur.execute("""
    SELECT description, transaction_date, debit_amount, credit_amount
    FROM banking_transactions
    WHERE account_number = '3648117'
    ORDER BY transaction_date
    LIMIT 5
""")
print("\nCIBC 3648117 sample transactions:")
for desc, date, debit, credit in cur.fetchall():
    print(f"  {date} | {desc[:60]} | D:{debit or 0:.2f} C:{credit or 0:.2f}")

cur.close()
conn.close()
