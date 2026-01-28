import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)

cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM invoices')
count = cur.fetchone()[0]
print(f'Current invoices table row count: {count}')

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='invoices' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print(f'All columns ({len(cols)}): {cols[:10]}...')

cur.close()
conn.close()
