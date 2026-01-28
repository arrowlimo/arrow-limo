import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)

cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'income_ledger' ORDER BY ordinal_position")
print('income_ledger columns:')
for row in cur.fetchall():
    print(f'  {row[0]}')
cur.close()
conn.close()
