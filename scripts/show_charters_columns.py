import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get charters table columns
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'charters'
    ORDER BY ordinal_position
""")

print("Charters table columns:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
