#!/usr/bin/env python
"""Verify GL distribution and ensure GL 9999 is empty."""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*80)
print("GL STATE CHECK")
print("="*80)

cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
gl9999 = cur.fetchone()[0]
print(f"GL 9999 count: {gl9999}")

cur.execute("""
    SELECT gl_account_code, COUNT(*) as cnt, ROUND(SUM(COALESCE(gross_amount,0))::numeric,2) as total
    FROM receipts
    GROUP BY gl_account_code
    ORDER BY cnt DESC
    LIMIT 20
""")

print("\nTop GL codes:")
for code, cnt, total in cur.fetchall():
    print(f"  GL {code}: {cnt} | ${float(total):,.2f}")

cur.close()
conn.close()
