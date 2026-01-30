#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 2.1-2.4: Backup LIMO tables and migrate unique columns to ALMS clients.
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

print("="*80)
print("PHASE 2.1-2.4: LIMO TABLES BACKUP & MIGRATION")
print("="*80)

# ============================================================================
# PHASE 2.1: Backup LIMO tables
# ============================================================================
print("\nPHASE 2.1: Backing up LIMO tables...")
print("-" * 80)

limo_tables = ['limo_clients', 'limo_clients_clean', 'limo_addresses', 'limo_addresses_clean']

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
    
    print(f"✅ {table:<25} {len(rows):>6,} records → {filename}")

# ============================================================================
# PHASE 2.2: Add columns to clients table
# ============================================================================
print("\nPHASE 2.2: Adding 4 columns to clients table...")
print("-" * 80)

try:
    cur.execute("""
        ALTER TABLE clients
        ADD COLUMN IF NOT EXISTS contact_person VARCHAR(255),
        ADD COLUMN IF NOT EXISTS data_issues TEXT,
        ADD COLUMN IF NOT EXISTS location_notes TEXT,
        ADD COLUMN IF NOT EXISTS service_preferences TEXT
    """)
    conn.commit()
    print("✅ Added columns: contact_person, data_issues, location_notes, service_preferences")
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    raise

# ============================================================================
# PHASE 2.3: Migrate limo_clients data to clients
# ============================================================================
print("\nPHASE 2.3: Migrating limo_clients data to ALMS clients...")
print("-" * 80)

try:
    # Migrate contact_person (81% populated)
    cur.execute("""
        UPDATE clients c
        SET contact_person = lc.contact_person
        FROM limo_clients lc
        WHERE c.client_id = lc.client_id
          AND lc.contact_person IS NOT NULL
          AND lc.contact_person != ''
    """)
    contact_updated = cur.rowcount
    
    # Migrate data_issues (53% populated)
    cur.execute("""
        UPDATE clients c
        SET data_issues = lc.data_issues
        FROM limo_clients lc
        WHERE c.client_id = lc.client_id
          AND lc.data_issues IS NOT NULL
          AND lc.data_issues != ''
    """)
    issues_updated = cur.rowcount
    
    # Migrate service_preferences (3.7% populated)
    cur.execute("""
        UPDATE clients c
        SET service_preferences = lc.service_preferences
        FROM limo_clients lc
        WHERE c.client_id = lc.client_id
          AND lc.service_preferences IS NOT NULL
          AND lc.service_preferences != ''
    """)
    prefs_updated = cur.rowcount
    
    conn.commit()
    print(f"✅ contact_person:        {contact_updated:>6,} records updated")
    print(f"✅ data_issues:           {issues_updated:>6,} records updated")
    print(f"✅ service_preferences:   {prefs_updated:>6,} records updated")
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    raise

# ============================================================================
# PHASE 2.4: Migrate limo_addresses.location_notes to clients
# ============================================================================
print("\nPHASE 2.4: Migrating limo_addresses location_notes to ALMS clients...")
print("-" * 80)

try:
    # Get max location_notes per client (most recent by address_id)
    cur.execute("""
        UPDATE clients c
        SET location_notes = la.location_notes
        FROM (
            SELECT DISTINCT ON (client_id) client_id, location_notes
            FROM limo_addresses
            WHERE location_notes IS NOT NULL AND location_notes != ''
            ORDER BY client_id, address_id DESC
        ) la
        WHERE c.client_id = la.client_id
    """)
    location_updated = cur.rowcount
    conn.commit()
    print(f"✅ location_notes:        {location_updated:>6,} records updated")
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    raise

print("\n" + "="*80)
print("✅ PHASES 2.1-2.4 COMPLETE: Backups created, data migrated to ALMS")
print("="*80)

cur.close()
conn.close()
