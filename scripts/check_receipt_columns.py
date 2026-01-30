#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'receipts' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print('Receipts columns:', ', '.join(cols))
cur.close()
conn.close()
