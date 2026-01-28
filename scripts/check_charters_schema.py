"""Check charters table schema."""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get column names
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns 
    WHERE table_name = 'charters'
    ORDER BY ordinal_position
""")

print("Charters table columns:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

# Check for client-related columns
cur.execute("""
    SELECT column_name
    FROM information_schema.columns 
    WHERE table_name = 'charters'
    AND column_name LIKE '%client%'
""")

print("\nClient-related columns:")
for row in cur.fetchall():
    print(f"  {row[0]}")

cur.close()
conn.close()
