import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)

cur = conn.cursor()
cur.execute("""
    SELECT description, COUNT(*) 
    FROM receipts 
    WHERE vendor_name='UNKNOWN' 
    GROUP BY description 
    ORDER BY COUNT(*) DESC 
    LIMIT 30
""")

print("\nRemaining UNKNOWN vendor descriptions:\n")
for desc, count in cur.fetchall():
    print(f'{count:4} | {desc[:70]}')

cur.close()
conn.close()
