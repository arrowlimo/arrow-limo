import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Columns:")
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")
cols = [r[0] for r in cur.fetchall()]
print(cols)

if 'created_at' in cols:
    cur.execute("""
        SELECT MAX(created_at) FROM banking_transactions
    """)
    print("\nLatest created_at:", cur.fetchone()[0])

# Show 5 most recent rows by transaction_id
print("\n5 most recent transaction_id rows:")
cur.execute("""
    SELECT transaction_id, account_number, transaction_date, description
    FROM banking_transactions
    ORDER BY transaction_id DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(row)

conn.close()
