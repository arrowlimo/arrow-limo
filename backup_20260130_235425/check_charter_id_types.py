import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT table_name, column_name, data_type 
    FROM information_schema.columns 
    WHERE column_name = 'charter_id' 
    AND table_name IN ('driver_payroll', 'charters')
""")

print("charter_id data types:")
for row in cur.fetchall():
    print(f"  {row[0]}.{row[1]}: {row[2]}")

# Also check reserve_number
cur.execute("""
    SELECT table_name, column_name, data_type 
    FROM information_schema.columns 
    WHERE column_name = 'reserve_number' 
    AND table_name IN ('driver_payroll', 'charters')
""")

print("\nreserve_number data types:")
for row in cur.fetchall():
    print(f"  {row[0]}.{row[1]}: {row[2]}")

cur.close()
conn.close()
