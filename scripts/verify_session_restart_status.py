#!/usr/bin/env python
"""Verify session restart status - Run checks 3-5 from CRITICAL CHECKLIST"""
import psycopg2
import os
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )

conn = get_db_connection()
cur = conn.cursor()

print("=" * 80)
print("SESSION RESTART VERIFICATION CHECKS")
print("=" * 80)

# Check 1: PostgreSQL health
cur.execute("SELECT pg_postmaster_start_time(), NOW() - pg_postmaster_start_time() as uptime")
start_time, uptime = cur.fetchone()
print(f"\n✓ Check 1: PostgreSQL Health")
print(f"  Started: {start_time}")
print(f"  Uptime: {uptime}")

# Check 3: Last Scotia Bank records (should be Dec 7, not Dec 8)
cur.execute("""
    SELECT COUNT(*), MAX(created_at)::date as last_created
    FROM banking_transactions 
    WHERE account_number = '903990106011'
""")
scotia_count, last_created = cur.fetchone()
print(f"\n✓ Check 3: Scotia Bank Records")
print(f"  Total records: {scotia_count}")
print(f"  Last created: {last_created}")
print(f"  Expected: Dec 7 (before midnight reboot)")

# Check 4: Fibrenew receipts (should be from Nov 28 backup)
cur.execute("""
    SELECT COUNT(*), MAX(created_at)::date as last_created
    FROM receipts 
    WHERE vendor_name ILIKE '%fibrenew%'
""")
fibrenew_count, last_created = cur.fetchone()
print(f"\n✓ Check 4: Fibrenew Receipts")
print(f"  Total receipts: {fibrenew_count}")
print(f"  Last created: {last_created}")
print(f"  Expected: Dec 6 or earlier (Dec 7 work LOST)")

# Check 5: Backup tables from Dec 7
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%backup_20251207%'
    ORDER BY table_name
""")
backups = cur.fetchall()
print(f"\n✓ Check 5: Dec 7 Backup Tables")
if backups:
    for (table,) in backups:
        print(f"  - {table}")
else:
    print(f"  No backup tables found from Dec 7")

cur.close()
conn.close()

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
