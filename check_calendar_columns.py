import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Check for calendar columns
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='charters' 
    AND column_name LIKE 'calendar%' 
    ORDER BY ordinal_position
""")

cols = cur.fetchall()
if cols:
    print("Calendar columns found:")
    for col in cols:
        print(f"  - {col[0]}")
else:
    print("❌ NO calendar columns found!")

cur.close()
conn.close()
