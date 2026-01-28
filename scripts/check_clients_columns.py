import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST','localhost'),
    dbname=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD','***REMOVED***')
)
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='clients' ORDER BY ordinal_position")
print('\n'.join([r[0] for r in cur.fetchall()]))
