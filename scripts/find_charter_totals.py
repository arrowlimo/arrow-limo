#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect('host=ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech dbname=neondb user=neondb_owner password=npg_89MbcFmZwUWo sslmode=require')
cur = conn.cursor()

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='charters' ORDER BY ordinal_position")
cols = [row[0] for row in cur.fetchall()]

print('Columns with total/amount:')
for col in cols:
    if 'total' in col.lower() or 'amount' in col.lower():
        print(f'  {col}')

cur.close()
conn.close()
