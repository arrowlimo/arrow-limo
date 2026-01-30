import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)
conn.autocommit = True
cur = conn.cursor()

# Get charters columns
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'charters'
    ORDER BY ordinal_position
""")

print("Charters columns:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

print("\nPayments columns:")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'payments'
    ORDER BY ordinal_position
""")

for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

conn.close()
