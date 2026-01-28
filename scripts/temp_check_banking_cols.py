import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")
print('=== BANKING_TRANSACTIONS COLUMNS ===')
for col in cur.fetchall():
    print(f'  {col[0]}: {col[1]}')

cur.close()
conn.close()
