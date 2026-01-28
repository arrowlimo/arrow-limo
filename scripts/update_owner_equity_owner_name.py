#!/usr/bin/env python3
"""Update owner name in owner_equity_accounts (dry-run by default)."""

import argparse
import psycopg2

parser = argparse.ArgumentParser(description="Rename owner in owner_equity_accounts")
parser.add_argument("--from", dest="old", default="Paul Heffner", help="Current owner name")
parser.add_argument("--to", dest="new", default="Paul Richard", help="New owner name")
parser.add_argument("--write", action="store_true", help="Apply changes")
args = parser.parse_args()

conn = psycopg2.connect(host="localhost", database="almsdata", user="postgres", password="***REMOVED***")
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM owner_equity_accounts WHERE owner_name = %s", (args.old,))
count = cur.fetchone()[0]

cur.execute("SELECT owner_name, account_type, current_balance FROM owner_equity_accounts WHERE owner_name = %s ORDER BY account_type", (args.old,))
rows = cur.fetchall()
print(f"Target rows: {count}")
for r in rows:
    print(f"  {r[0]} | {r[1]} | ${r[2]:,.2f}")

if not args.write:
    print("\nDry-run: no changes applied.")
    cur.close(); conn.close()
else:
    try:
        cur.execute("UPDATE owner_equity_accounts SET owner_name = %s WHERE owner_name = %s", (args.new, args.old))
        affected = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        print(f"Committed: {affected} rows updated to owner_name={args.new}")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
    finally:
        cur.close(); conn.close()
