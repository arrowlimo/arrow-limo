import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

print("="*100)
print("CHECKING LARGE TRANSACTIONS IN JANUARY 2012")
print("="*100)

cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions 
    WHERE transaction_id BETWEEN 54704 AND 54707
    ORDER BY transaction_id
""")

print("\nTransaction ID | Date       | Description                              | Debit      | Credit")
print("-"*100)
for row in cur.fetchall():
    tid, date, desc, debit, credit = row
    print(f"{tid:14} | {date} | {desc[:40]:40} | {debit or 0:10.2f} | {credit or 0:10.2f}")

print("\n" + "="*100)
print("CHECKING FOR ANY TRANSACTIONS OVER $100,000")
print("="*100)

cur.execute("""
    SELECT transaction_id, transaction_date, account_number, description, 
           debit_amount, credit_amount
    FROM banking_transactions 
    WHERE account_number = '903990106011'
      AND (debit_amount > 100000 OR credit_amount > 100000)
    ORDER BY transaction_date, transaction_id
""")

print("\nID     | Date       | Debit        | Credit       | Description")
print("-"*100)
rows = cur.fetchall()
for row in rows:
    tid, date, acct, desc, debit, credit = row
    print(f"{tid:6} | {date} | {debit or 0:12.2f} | {credit or 0:12.2f} | {desc[:50]}")

print(f"\nTotal large transactions found: {len(rows)}")

cur.close()
conn.close()
