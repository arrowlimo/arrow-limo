#!/usr/bin/env python
"""Print remaining GL 9999 entries for review."""

import psycopg2
import os
import json
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, description,
           banking_transaction_id, created_from_banking, category, gl_account_code,
           source_system, source_file
    FROM receipts
    WHERE gl_account_code = '9999'
""")
rows = cur.fetchall()

print(f"Remaining GL 9999 entries: {len(rows)}\n")
for r in rows:
    print(json.dumps({
        "receipt_id": r[0],
        "receipt_date": r[1].isoformat() if r[1] else None,
        "vendor_name": r[2],
        "gross_amount": float(r[3]) if r[3] is not None else None,
        "description": r[4],
        "banking_transaction_id": r[5],
        "created_from_banking": r[6],
        "category": r[7],
        "gl_account_code": r[8],
        "source_system": r[9],
        "source_file": r[10],
    }, indent=2))

cur.close()
conn.close()
