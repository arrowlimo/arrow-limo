import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Check which T4 box columns exist
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'driver_payroll' AND column_name LIKE 't4_box_%'
    ORDER BY column_name
""")
print("T4 box columns in driver_payroll:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
