#!/usr/bin/env python3
import os, psycopg2
conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'square_payouts' ORDER BY ordinal_position")
print('square_payouts columns:')
for row in cur.fetchall():
    print(f"  {row[0]}")
