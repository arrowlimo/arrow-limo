#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2: Backup LIMO tables (no migration), then drop everything.
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

limo_tables = ['limo_clients', 'limo_clients_clean', 'limo_addresses', 'limo_addresses_clean']

print("="*80)
print("PHASE 2: BACKUP & DROP LIMO TABLES (no migration)")
print("="*80)

# Backup
print("\n1. BACKUP:")
print("-" * 80)

for table in limo_tables:
    cur.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = '{table}' ORDER BY ordinal_position
    """)
    columns = [r[0] for r in cur.fetchall()]
    
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    
    filename = f"{backup_dir}/{table}_backup_{timestamp}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    print(f"✅ {table:<25} {len(rows):>7,} records → {filename}")

# Drop views first
print("\n2. DROP DEPENDENT VIEWS:")
print("-" * 80)

views_to_drop = [
    'client_directory',
    'client_directory_clean',
    'client_locations_clean',
    'service_preferences',
    'service_preferences_clean',
    'data_quality_issues'
]

for view in views_to_drop:
    try:
        cur.execute(f"DROP VIEW IF EXISTS {view} CASCADE")
        conn.commit()
        print(f"✅ {view}")
    except Exception as e:
        print(f"⚠️  {view}: {e}")
        conn.rollback()

# Drop tables
print("\n3. DROP LIMO TABLES:")
print("-" * 80)

for table in limo_tables:
    try:
        cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        conn.commit()
        print(f"✅ {table}")
    except Exception as e:
        print(f"❌ {table}: {e}")
        conn.rollback()

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ PHASE 2 COMPLETE")
print("="*80)
