#!/usr/bin/env python3
"""Verify whether credit_lines and credit_lines_overview exist; show row count if present."""

import psycopg2

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
cur = conn.cursor()

cur.execute("""
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema='public' AND table_name='credit_lines'
)
""")
exists = cur.fetchone()[0]

cur.execute("""
SELECT EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema='public' AND table_name='credit_lines_overview'
)
""")
oview_exists = cur.fetchone()[0]

print(f"credit_lines exists: {exists}")
print(f"credit_lines_overview exists: {oview_exists}")

if exists:
    cur.execute("SELECT COUNT(*) FROM credit_lines")
    print(f"credit_lines row count: {cur.fetchone()[0]}")

cur.close(); conn.close()
