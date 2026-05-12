import os
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.getenv('ALMS_DB_PASSWORD', ''),
    port=5432
)
cursor = conn.cursor()

cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name ILIKE '%invoice%' ORDER BY table_name")

print('=== INVOICE-RELATED TABLES ===\n')
for table in cursor.fetchall():
    table_name = table[0]
    cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
    count = cursor.fetchone()[0]
    print(f'{table_name}: {count:,} records')

conn.close()
