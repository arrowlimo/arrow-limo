#!/usr/bin/env python3
"""List orphan charters (NULL client_id)"""

import os
import psycopg2

conn = psycopg2.connect(
    host='localhost', dbname='almsdata', user='postgres',
    password=os.environ.get('DB_PASSWORD', '***REDACTED***')
)
cur = conn.cursor()

# Get first 20 orphan charters
cur.execute('''
    SELECT ch.charter_id, ch.reserve_number, ch.charter_date, ch.total_amount_due
    FROM charters ch
    WHERE ch.client_id IS NULL
    ORDER BY ch.charter_date DESC
    LIMIT 20
''')

print("First 20 orphan charters (no client_id):")
for cid, reserve_no, date, amount in cur.fetchall():
    print(f"  Charter {cid}: Reserve {reserve_no} | {date} | ${amount}")

cur.close()
conn.close()
