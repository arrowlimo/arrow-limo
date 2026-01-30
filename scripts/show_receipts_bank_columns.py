import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='receipts' 
    AND column_name LIKE '%bank%'
    ORDER BY ordinal_position
""")

print("receipts bank-related columns:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
