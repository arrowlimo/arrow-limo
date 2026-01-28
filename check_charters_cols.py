import psycopg2

conn = psycopg2.connect(host='localhost', port='5432', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get all charters columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position")
cols = [c[0] for c in cur.fetchall()]

print("All CHARTERS columns:")
for i, col in enumerate(cols, 1):
    print(f"  {i:2}. {col}")

cur.close()
conn.close()
