import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Check clients table
print("Clients table columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='clients' ORDER BY ordinal_position")
for col in cur.fetchall():
    print(f"  - {col[0]}")

# Check first row
cur.execute("SELECT * FROM clients LIMIT 1")
print(f"\nFirst client row columns: {[desc[0] for desc in cur.description]}")
row = cur.fetchone()
print(f"First client data: {row}")

cur.close()
conn.close()
