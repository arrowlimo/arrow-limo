#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', password='***REDACTED***', database='almsdata')
cur = conn.cursor()

# Check 2014-2017 summary by account number
cur.execute("""
    SELECT account_number, EXTRACT(YEAR FROM transaction_date) as year, 
           COUNT(*) as count, MIN(balance) as min_balance, MAX(balance) as max_balance
    FROM banking_transactions 
    WHERE account_number IN ('1615', '61615') 
    AND EXTRACT(YEAR FROM transaction_date) >= 2014
    GROUP BY account_number, EXTRACT(YEAR FROM transaction_date)
    ORDER BY account_number, year
""")

print("CIBC Account 1615 - 2014-2017 Summary:")
for row in cur.fetchall():
    acct, year, count, min_bal, max_bal = row
    print(f"  Account {acct}, Year {int(year)}: {count} txns, Range: {min_bal} to {max_bal}")

# Check specific balances
print("\nSpecific balance verification:")
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions 
    WHERE account_number = '1615'
    AND balance IN (-4221.09, -4296.38, -5197.99)
    ORDER BY transaction_date
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:<30} Bal: {row[2]}")

# Check for target dates
print("\nTarget date verification:")
for year, month, expected_bal in [(2015, 1, -4221.09), (2015, 12, -5197.99), (2016, 1, -5197.99)]:
    cur.execute(f"""
        SELECT transaction_date, description, balance
        FROM banking_transactions 
        WHERE account_number = '1615'
        AND EXTRACT(YEAR FROM transaction_date) = {year}
        AND EXTRACT(MONTH FROM transaction_date) = {month}
        AND description = 'Opening balance'
        LIMIT 1
    """)
    result = cur.fetchone()
    if result:
        print(f"  {result[0]}: {result[1]} = {result[2]}")
    else:
        print(f"  {year}-{month:02d}: NOT FOUND (expected {expected_bal})")

cur.close()
conn.close()
