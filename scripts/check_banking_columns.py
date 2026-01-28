import psycopg2

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    ORDER BY ordinal_position
""")

print("banking_transactions columns:")
for col_name, col_type in cur.fetchall():
    print(f"  {col_name:30} {col_type}")

cur.close()
conn.close()
