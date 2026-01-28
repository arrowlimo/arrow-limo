#!/usr/bin/env python3
"""Search unified_general_ledger for likely Bank and Petty Cash account codes."""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST','localhost'),
    database=os.environ.get('DB_NAME','almsdata'),
    user=os.environ.get('DB_USER','postgres'),
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("Candidate BANK accounts (name/code contains 'cibc' or 'bank' or 'checking'):")
cur.execute("""
    SELECT DISTINCT account_code, COALESCE(account_name,'') AS name
    FROM unified_general_ledger
    WHERE LOWER(account_code) ~ '(cibc|checking|chequing|bank|scotia)'
       OR LOWER(COALESCE(account_name,'')) ~ '(cibc|checking|chequing|bank|scotia)'
    ORDER BY account_code
    LIMIT 50
""")
for r in cur.fetchall():
    print(f"  {r['account_code']} | {r['name']}")

print("\nCandidate PETTY CASH accounts (name/code contains 'petty' or 'cash on hand'):")
cur.execute("""
    SELECT DISTINCT account_code, COALESCE(account_name,'') AS name
    FROM unified_general_ledger
    WHERE LOWER(account_code) ~ '(petty|cash on hand|cash-on-hand|cash\s*on\s*hand)'
       OR LOWER(COALESCE(account_name,'')) ~ '(petty|cash on hand|cash-on-hand|cash\s*on\s*hand)'
    ORDER BY account_code
    LIMIT 50
""")
petty = cur.fetchall()
if petty:
    for r in petty:
        print(f"  {r['account_code']} | {r['name']}")
else:
    print("  (no obvious petty cash account found)")

print("\nOther CASH-like accounts (contains 'cash'):")
cur.execute("""
    SELECT DISTINCT account_code, COALESCE(account_name,'') AS name
    FROM unified_general_ledger
    WHERE LOWER(account_code) LIKE '%cash%'
       OR LOWER(COALESCE(account_name,'')) LIKE '%cash%'
    ORDER BY account_code
    LIMIT 50
""")
for r in cur.fetchall():
    print(f"  {r['account_code']} | {r['name']}")

cur.close(); conn.close()
