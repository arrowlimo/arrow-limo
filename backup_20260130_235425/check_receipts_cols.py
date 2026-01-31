import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")

print("Receipts table columns:")
for col, dtype in cur.fetchall():
    print(f"  - {col}: {dtype}")

cur.close()
conn.close()
