#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("SELECT * FROM banking_transactions LIMIT 1")
cols = [desc[0] for desc in cur.description]
print('Banking Transaction Columns:')
for col in cols:
    print(f'  - {col}')
cur.close()
conn.close()
