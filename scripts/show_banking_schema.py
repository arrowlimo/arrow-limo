import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='banking_transactions' 
    ORDER BY ordinal_position
""")
print("=== banking_transactions columns ===")
for row in cur.fetchall():
    print(f"{row[0]:30} {row[1]}")

cur.close()
conn.close()
