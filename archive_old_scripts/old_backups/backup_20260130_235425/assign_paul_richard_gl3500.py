#!/usr/bin/env python
"""Assign PAUL RICHARD entries to GL 3500 (Owner Draw)."""

import psycopg2
import os
import json
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*80)
print("ASSIGNING PAUL RICHARD → GL 3500 (Owner Draw)")
print("="*80)

# Backup before update
cur.execute("""
    SELECT json_agg(row_to_json(t))
    FROM (
        SELECT receipt_id, vendor_name, gross_amount, gl_account_code
        FROM receipts
        WHERE vendor_name = 'PAUL RICHARD' AND gl_account_code = '9999'
    ) t
""")

backup_data = cur.fetchone()[0]
backup_path = f"backups/paul_richard_assignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
os.makedirs('backups', exist_ok=True)

with open(backup_path, 'w') as f:
    json.dump(backup_data, f, indent=2)

# Update to GL 3500
cur.execute("""
    UPDATE receipts
    SET gl_account_code = '3500'
    WHERE vendor_name = 'PAUL RICHARD' AND gl_account_code = '9999'
""")

count = cur.rowcount
conn.commit()

print(f"✅ Updated {count} PAUL RICHARD entries to GL 3500")
print(f"✅ Backup: {backup_path}")

# Show remaining GL 9999 count
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
remaining = cur.fetchone()[0]
print(f"\n📊 Remaining GL 9999 entries: {remaining}")

cur.close()
conn.close()
