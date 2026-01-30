import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()

cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='banking_transactions' 
    ORDER BY ordinal_position
""")

print("banking_transactions columns:")
for row in cur.fetchall():
    print(f"  - {row[0]}")

cur.close()
conn.close()
