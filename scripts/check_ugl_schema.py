#!/usr/bin/env python3
import psycopg2, os

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("unified_general_ledger columns:")
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'unified_general_ledger' ORDER BY ordinal_position")
for r in cur.fetchall():
    print(f"  {r[0]}")

print("\nSample UGL data:")
cur.execute("SELECT transaction_date, account_code, debit_amount, credit_amount, description FROM unified_general_ledger LIMIT 5")
for r in cur.fetchall():
    print(f"{r[0]} | Code:{r[1]} | Dr:${r[2] or 0} Cr:${r[3] or 0} | {(r[4] or '')[:40]}")
