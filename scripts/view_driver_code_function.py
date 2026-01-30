import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

# Get function definition
cur.execute("""
    SELECT pg_get_functiondef(oid) 
    FROM pg_proc 
    WHERE proname = 'auto_assign_driver_code'
""")
result = cur.fetchone()
if result:
    print("Function auto_assign_driver_code:")
    print(result[0])
else:
    print("Function not found")

cur.close()
conn.close()
