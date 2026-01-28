import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get all columns in receipts table
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='receipts' 
    ORDER BY ordinal_position
""")

print("RECEIPTS TABLE COLUMNS:")
for col_name, data_type in cur.fetchall():
    print(f"  {col_name}: {data_type}")

cur.close()
conn.close()
