import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("employee_pay_entries columns:")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'employee_pay_entries' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"  {row[0]} ({row[1]})")

cur.close()
conn.close()
