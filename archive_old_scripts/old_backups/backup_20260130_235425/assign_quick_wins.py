#!/usr/bin/env python
"""Assign quick wins: Withdrawals, Food vendors, Radiator."""

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

print("\n" + "="*100)
print("ASSIGNING QUICK WINS")
print("="*100)

assignments = [
    ('WITHDRAWAL IBB', '3650', 'Cash Withdrawal'),
    ('NORTHLAND RADIATOR', '4000', 'Vehicle Maintenance'),
    ('A&W', '6800', 'Meals & Entertainment'),
    ('ARBYS', '6800', 'Meals & Entertainment'),
    ('7 ELEVEN', '6800', 'Meals & Entertainment'),
    ('GEORGE\'S PIZZA', '6800', 'Meals & Entertainment'),
]

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
total_assigned = 0

for vendor, gl_code, desc in assignments:
    # Backup before update
    cur.execute("""
        SELECT json_agg(row_to_json(t))
        FROM (
            SELECT receipt_id, vendor_name, gross_amount, gl_account_code
            FROM receipts
            WHERE vendor_name = %s AND gl_account_code = '9999'
        ) t
    """, (vendor,))

    backup_data = cur.fetchone()[0]
    if backup_data:
        backup_path = f"backups/{vendor.lower().replace(' ', '_')}_to_gl{gl_code}_{timestamp}.json"
        os.makedirs('backups', exist_ok=True)

        with open(backup_path, 'w') as f:
            json.dump(backup_data, f, indent=2)

        # Update to new GL code
        cur.execute("""
            UPDATE receipts
            SET gl_account_code = %s
            WHERE vendor_name = %s AND gl_account_code = '9999'
        """, (gl_code, vendor))

        count = cur.rowcount
        conn.commit()
        total_assigned += count

        print(f"✅ {vendor:<30} {count:>2} entries → GL {gl_code} ({desc})")

# Show remaining GL 9999 count
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
remaining = cur.fetchone()[0]

print(f"\n{'='*100}")
print(f"📊 Assigned: {total_assigned} entries")
print(f"📊 Remaining GL 9999: {remaining} entries")
print(f"{'='*100}")

cur.close()
conn.close()
