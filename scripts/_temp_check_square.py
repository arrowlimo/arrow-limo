import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find Square tables
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE '%square%' ORDER BY table_name")
tables = [row[0] for row in cur.fetchall()]
print("Square tables:", tables)

# Check Square deposits pattern
cur.execute("""
    SELECT COUNT(*), SUM(credit_amount), MIN(transaction_date), MAX(transaction_date)
    FROM banking_transactions
    WHERE description ILIKE '%SQUARE%'
    AND credit_amount > 0
""")
print("\nSquare deposits:", cur.fetchone())

# Check if Square transactions table exists
if 'square_transactions' in tables:
    cur.execute("SELECT COUNT(*) FROM square_transactions")
    print(f"Square transactions: {cur.fetchone()[0]:,}")

conn.close()
