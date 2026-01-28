import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()

# Check Scotia account numbers
cur.execute("""
    SELECT DISTINCT account_number 
    FROM banking_transactions 
    WHERE account_number LIKE '%903990%'
    ORDER BY account_number
""")

print("Scotia account numbers in database:")
for row in cur.fetchall():
    print(f"  {row[0]}")

# Check the $49.05 transaction
cur.execute("""
    SELECT transaction_id, transaction_date, account_number, description, debit_amount
    FROM banking_transactions 
    WHERE transaction_date BETWEEN '2012-09-12' AND '2012-09-20'
      AND debit_amount = 49.05
""")

print("\n$49.05 transactions in date range:")
for row in cur.fetchall():
    print(f"  ID={row[0]}, Date={row[1]}, Account={row[2]}, Desc={row[3]}, Debit=${row[4]}")

conn.close()
