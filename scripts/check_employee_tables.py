import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)

cur = conn.cursor()
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name LIKE 'employee%'
    ORDER BY table_name
""")

tables = cur.fetchall()
print(f"Found {len(tables)} employee tables:")
for table in tables:
    print(f"  - {table[0]}")

if not tables:
    print("\nNeed to run migration: migrations/2025-10-21_create_non_charter_employee_booking_system.sql")

cur.close()
conn.close()
