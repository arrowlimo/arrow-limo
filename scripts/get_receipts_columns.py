import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")

print("RECEIPTS TABLE COLUMNS:")
print("=" * 60)
for row in cur.fetchall():
    print(f"{row[0]:30} {row[1]}")

cur.close()
conn.close()
