"""
Check receipts table structure for GL code columns
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

# Get column info
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns
    WHERE table_name = 'receipts'
    AND column_name LIKE '%gl%' OR column_name LIKE '%account%' OR column_name LIKE '%code%'
    ORDER BY ordinal_position
""")

print("=" * 100)
print("RECEIPTS TABLE - GL/ACCOUNT/CODE COLUMNS")
print("=" * 100)
for col, dtype, maxlen in cur.fetchall():
    print(f"{col:<40} {dtype:<20} {maxlen if maxlen else ''}")

# Check if there's a GL codes table
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%gl%'
    OR table_name LIKE '%account%'
    OR table_name LIKE '%chart%'
    ORDER BY table_name
""")

print("\n" + "=" * 100)
print("POTENTIAL GL/ACCOUNT TABLES")
print("=" * 100)
tables = cur.fetchall()
if tables:
    for (tbl,) in tables:
        print(f"- {tbl}")
else:
    print("No GL/account tables found")

cur.close()
conn.close()
