import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Test the exact SELECT query
try:
    cur.execute("""
        SELECT transaction_id, transaction_date, credit_amount, debit_amount,
               description
        FROM banking_transactions
        WHERE reconciled_payment_id IS NULL
        LIMIT 5
    """)
    print(f"✅ Query successful. Columns present.")
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print(f"❌ Query failed: {e}")

cur.close()
conn.close()
