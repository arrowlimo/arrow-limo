#!/usr/bin/env python
import psycopg2
conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

tables = ['limo_clients', 'limo_clients_clean', 'limo_addresses', 'limo_addresses_clean']

for table in tables:
    cur.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}' ORDER BY ordinal_position
    """)
    cols = [r[0] for r in cur.fetchall()]
    print(f"\n{table}:")
    print("  " + ", ".join(cols))

cur.close()
conn.close()
