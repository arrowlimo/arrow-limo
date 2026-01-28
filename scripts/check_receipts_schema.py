import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', '5432')),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='receipts' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f"{row[0]}: {row[1]}")
cur.close()
conn.close()
