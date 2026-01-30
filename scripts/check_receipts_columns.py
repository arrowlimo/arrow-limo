import psycopg2

conn = psycopg2.connect(dbname='almsdata', user='postgres', password='***REDACTED***', host='localhost')
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")

print("receipts table columns:")
for col_name, col_type in cur.fetchall():
    print(f"  {col_name:30} {col_type}")

cur.close()
conn.close()
