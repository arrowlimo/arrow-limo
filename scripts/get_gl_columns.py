"""Get general_ledger column names"""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'general_ledger'
    ORDER BY ordinal_position
""")

print("general_ledger columns:")
for col, dtype in cur.fetchall():
    print(f"  {col}: {dtype}")

conn.close()
