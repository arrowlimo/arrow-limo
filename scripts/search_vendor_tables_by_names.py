#!/usr/bin/env python
import psycopg2, os

conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REDACTED***'))
cur = conn.cursor()

for table, col in [('vendor_accounts','canonical_vendor'),('vendor_accounts','display_name'),('vendors','vendor_name'),('vendors','company_name')]:
    for n in ['Heffner Circle','Heffner Circle Service','Ike Tineo']:
        try:
            cur.execute(f"SELECT * FROM {table} WHERE {col} ILIKE %s ORDER BY {col} LIMIT 10", (f"%{n}%",))
            rows = cur.fetchall()
            print(f"{table}.{col} LIKE {n}: {len(rows)}")
            for r in rows:
                print(r)
        except Exception as e:
            print(f"Query failed for {table}.{col} with {n}: {e}")

cur.close(); conn.close()
