#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1.1: Backup limo_contacts, lms_charges, lms_deposits as CSV exports.
"""
import psycopg2
import csv
import os
from datetime import datetime

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

backup_dir = 'reports/legacy_table_backups'
os.makedirs(backup_dir, exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

tables_to_backup = [
    'limo_contacts',
    'lms_charges',
    'lms_deposits'
]

print("="*80)
print("PHASE 1.1: BACKUP LEGACY TABLES")
print("="*80)

for table in tables_to_backup:
    # Get all columns
    cur.execute(f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    columns = [r[0] for r in cur.fetchall()]
    
    # Get all data
    cur.execute(f"SELECT * FROM {table} ORDER BY 1")
    rows = cur.fetchall()
    
    # Write to CSV
    filename = f"{backup_dir}/{table}_backup_{timestamp}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    print(f"\n✅ {table}")
    print(f"   Records: {len(rows):,}")
    print(f"   Backup: {filename}")

cur.close()
conn.close()

print("\n" + "="*80)
print(f"✅ Backups complete. Safe to proceed with deletions.")
print("="*80)
