import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get table structure
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='charters'
    ORDER BY ordinal_position
""")

columns = cur.fetchall()
print("CHARTERS TABLE COLUMNS:")
for col in columns:
    print(f"  {col[0]}: {col[1]}")

cur.close()
conn.close()
