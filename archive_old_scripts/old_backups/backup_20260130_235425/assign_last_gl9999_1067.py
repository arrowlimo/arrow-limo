#!/usr/bin/env python
"""Assign remaining GL 9999 entry (106.7 THE DRIVE) to GL 6200 (Advertising/Marketing)."""

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
print("ASSIGN 106.7 THE DRIVE → GL 6200 (Advertising)")
print("="*80)

# Backup remaining GL 9999 entries
cur.execute("""
    SELECT json_agg(row_to_json(t))
    FROM (
        SELECT * FROM receipts
        WHERE gl_account_code = '9999'
    ) t
""")
backup = cur.fetchone()[0]
count_backup = len(backup) if backup else 0

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
os.makedirs('backups', exist_ok=True)
backup_path = f"backups/last_gl9999_backup_{timestamp}.json"
with open(backup_path, 'w', encoding='utf-8') as f:
    json.dump(backup, f, indent=2, default=str)
print(f"Backup saved: {backup_path} ({count_backup} entries)")

# Update
cur.execute(
    """
    UPDATE receipts
    SET gl_account_code = '6200'
    WHERE gl_account_code = '9999'
    """
)
updated = cur.rowcount
conn.commit()

print(f"✅ Updated {updated} entry to GL 6200")

# Check remaining
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
remaining = cur.fetchone()[0]
print(f"📊 Remaining GL 9999 entries: {remaining}")

cur.close()
conn.close()
