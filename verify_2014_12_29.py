import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check for the 2014-12-29 G-49416 transaction
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
      AND transaction_date = '2014-12-29'
    ORDER BY transaction_id
""")

rows = cur.fetchall()

if rows:
    print(f"✅ Found {len(rows)} transaction(s) on 2014-12-29:")
    for row in rows:
        print(f"   ID {row[0]}: {row[1]} | {row[2][:60]}")
        print(f"   Debit: ${row[3] if row[3] else 0:.2f}, Credit: ${row[4] if row[4] else 0:.2f}, Balance: ${row[5] if row[5] else 0:.2f}")
else:
    print("❌ No transactions found for 2014-12-29")

# Also check total 2014 transactions
cur.execute("""
    SELECT COUNT(*) 
    FROM banking_transactions 
    WHERE account_number = '903990106011' 
      AND EXTRACT(YEAR FROM transaction_date) = 2014
""")
count = cur.fetchone()[0]
print(f"\n📊 Total 2014 Scotia transactions: {count}")

cur.close()
conn.close()
