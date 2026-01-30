"""Check 2014 opening balance specifically."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

# Check 2013 closing
cur.execute("""
    SELECT balance FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
""")
result_2013 = cur.fetchone()
print(f"2013 last transaction balance: ${result_2013[0] if result_2013[0] is not None else 'NULL'}")

# Check 2014 opening markers
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE account_number = '1615'
    AND EXTRACT(YEAR FROM transaction_date) = 2014
    AND description LIKE 'Opening%'
    LIMIT 1
""")
result_2014 = cur.fetchone()
if result_2014:
    print(f"2014 opening marker: {result_2014[0]} | {result_2014[1]} | ${result_2014[2]}")
else:
    print("No 2014 opening marker found")

conn.close()
