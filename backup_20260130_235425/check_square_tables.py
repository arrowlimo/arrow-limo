import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    dbname=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public' 
      AND table_name LIKE '%square%'
    ORDER BY table_name
""")
tables = cur.fetchall()
print('Square-related tables:')
for t in tables:
    print(f'  {t[0]}')
cur.close()
conn.close()
