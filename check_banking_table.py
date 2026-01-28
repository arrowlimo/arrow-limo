import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check if banking_transactions exists
cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='banking_transactions')")
exists = cur.fetchone()[0]
print(f"banking_transactions exists: {exists}")

if exists:
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='banking_transactions' ORDER BY ordinal_position")
    cols = [row[0] for row in cur.fetchall()]
    print(f"Columns: {cols}")
    
    # Check for pk column
    cur.execute("""SELECT column_name FROM information_schema.columns 
        WHERE table_name='banking_transactions' AND column_name LIKE '%id%' LIMIT 1""")
    pk_col = cur.fetchone()
    print(f"Primary key column: {pk_col[0] if pk_col else 'NOT FOUND'}")

cur.close()
conn.close()
