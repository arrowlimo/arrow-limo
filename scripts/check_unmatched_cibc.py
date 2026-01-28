#!/usr/bin/env python3
import psycopg2, os

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("cibc_ledger_staging (53 rows) - Sample:")
cur.execute('SELECT txn_date, amount, txn_type, description FROM cibc_ledger_staging ORDER BY txn_date LIMIT 10')
for r in cur.fetchall():
    print(f"  {r[0]} | ${r[1]:,.2f} | {r[2]:10} | {(r[3] or 'N/A')[:40]}")

print("\ncibc_qbo_staging (1,200 rows) - Sample:")
cur.execute('SELECT dtposted, trnamt, trntype, name, memo FROM cibc_qbo_staging ORDER BY dtposted LIMIT 10')
for r in cur.fetchall():
    print(f"  {r[0]} | ${r[1]:,.2f} | {(r[2] or 'N/A'):10} | {(r[3] or 'N/A')[:30]}")
