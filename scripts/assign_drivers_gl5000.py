#!/usr/bin/env python
"""Assign LARRY TAYLOR and JESSE GORDON to GL 5000 (Driver Pay)."""

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

print("\n" + "="*80)
print("ASSIGNING DRIVERS → GL 5000 (Driver Pay)")
print("="*80)

drivers = [('LARRY TAYLOR', '$2,485'), ('JESSE GORDON', '$5,541')]

for driver, amount in drivers:
    # Backup before update
    cur.execute("""
        SELECT json_agg(row_to_json(t))
        FROM (
            SELECT receipt_id, vendor_name, gross_amount, gl_account_code
            FROM receipts
            WHERE vendor_name = %s AND gl_account_code = '9999'
        ) t
    """, (driver,))

    backup_data = cur.fetchone()[0]
    backup_path = f"backups/{driver.lower().replace(' ', '_')}_assignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs('backups', exist_ok=True)

    with open(backup_path, 'w') as f:
        json.dump(backup_data, f, indent=2)

    # Update to GL 5000
    cur.execute("""
        UPDATE receipts
        SET gl_account_code = '5000'
        WHERE vendor_name = %s AND gl_account_code = '9999'
    """, (driver,))

    count = cur.rowcount
    conn.commit()

    print(f"✅ Updated {count} {driver} entries ({amount}) to GL 5000")
    print(f"   Backup: {backup_path}")

# Show remaining GL 9999 count
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
remaining = cur.fetchone()[0]
print(f"\n📊 Remaining GL 9999 entries: {remaining}")

cur.close()
conn.close()
