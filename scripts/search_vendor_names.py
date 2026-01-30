#!/usr/bin/env python
import psycopg2, os

conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REDACTED***'))
cur = conn.cursor()

names = ['Heffner Circle','Heffner Circle Service','Ike Tineo']
for table in ['vendor_accounts','vendors']:
    print(f'\n=== {table} ===')
    for n in names:
        try:
            cur.execute(f"SELECT * FROM {table} WHERE name ILIKE %s ORDER BY name LIMIT 10", (f"%{n}%",))
            print(n+':', cur.fetchall())
        except Exception as e:
            print(table, 'query failed:', e)

cur.close(); conn.close()
