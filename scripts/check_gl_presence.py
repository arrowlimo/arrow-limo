#!/usr/bin/env python3
import psycopg2

TABLES = [
    'receipts',
    'payments',
    'banking_transactions',
    'invoices',
    'journal_lines',
]

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
for t in TABLES:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position",
        (t,),
    )
    cols = [r[0] for r in cur.fetchall()]
    print(f"{t}: {', '.join(cols)}")
cur.close()
conn.close()
