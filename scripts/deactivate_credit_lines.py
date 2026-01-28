#!/usr/bin/env python3
"""Deactivate credit_lines (set is_active=false) - dry-run by default."""

import argparse
import psycopg2

parser = argparse.ArgumentParser(description="Deactivate credit_lines")
parser.add_argument("--write", action="store_true", help="Apply changes")
args = parser.parse_args()

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM credit_lines WHERE COALESCE(is_active, true) = true")
active = cur.fetchone()[0]
cur.execute("SELECT account_name, bank_name, credit_limit, current_balance FROM credit_lines WHERE COALESCE(is_active, true) = true ORDER BY account_name")
rows = cur.fetchall()
print(f"Active credit_lines: {active}")
for r in rows:
    print(f"  {r[0]:30} | {r[1]:20} | Limit ${r[2]:,.2f} | Balance ${r[3]:,.2f}")

if not args.write:
    print("\nDry-run: no changes applied.")
    cur.close(); conn.close()
else:
    try:
        cur.execute("UPDATE credit_lines SET is_active = false WHERE COALESCE(is_active, true) = true")
        affected = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        print(f"Committed: {affected} rows deactivated.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
    finally:
        cur.close(); conn.close()
