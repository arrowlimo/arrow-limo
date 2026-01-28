import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)

cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' AND column_name='reserve_number'")
result = cur.fetchone()
print('reserve_number column exists:', result is not None)

cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='invoices')")
invoices_exists = cur.fetchone()[0]
print('invoices table exists:', invoices_exists)

cur.close()
conn.close()
