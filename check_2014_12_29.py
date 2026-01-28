import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check for the 2014-12-29 transaction
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, balance 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
      AND transaction_date = '2014-12-29'
""")

rows = cur.fetchall()

if rows:
    print(f"✅ Found {len(rows)} transaction(s) on 2014-12-29:")
    for row in rows:
        print(f"   ID {row[0]}: {row[2]}, Debit: ${row[3]}, Balance: ${row[4]}")
else:
    print("❌ Transaction not found in database")

cur.close()
conn.close()
