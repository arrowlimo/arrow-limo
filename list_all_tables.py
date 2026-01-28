import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema='public' ORDER BY table_name
""")

print("PUBLIC TABLES:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
