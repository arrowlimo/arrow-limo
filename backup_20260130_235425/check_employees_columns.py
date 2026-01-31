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
    WHERE table_name = 'employees' 
    ORDER BY ordinal_position
""")

print("Employees table columns:")
for row in cur.fetchall():
    print(f"  {row[0]} ({row[1]})")

cur.close()
conn.close()
