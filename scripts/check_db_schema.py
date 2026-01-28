import psycopg2

conn = psycopg2.connect(
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***',
    host='localhost'
)

cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'journal'")
columns = [row[0] for row in cur.fetchall()]
print("Journal table columns:")
for col in columns:
    print(f"- {col}")

# Check a sample of data
print("\nSample data from journal table:")
cur.execute("SELECT * FROM journal LIMIT 5")
rows = cur.fetchall()
for row in rows:
    print(row)

conn.close()