#!/usr/bin/env python3
"""
Restore from the backup SQL file and re-run the fix.
"""

import os
import psycopg2
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

backup_file = "reports/employee_pay_master_backup_cpp_fix_comprehensive_20260123_192905.sql"

if not os.path.exists(backup_file):
    print(f"❌ Backup file not found: {backup_file}")
    exit(1)

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)
cur = conn.cursor()

print("="*90)
print("RESTORE FROM BACKUP AND RE-RUN FIX")
print("="*90)

print(f"\n1️⃣  Reading backup file...")
try:
    with open(backup_file, 'r') as f:
        backup_sql = f.read()
    print(f"   ✅ Read {len(backup_sql)} bytes from backup")
except Exception as e:
    print(f"   ❌ Failed to read backup: {e}")
    exit(1)

print(f"\n2️⃣  Restoring from backup...")
try:
    cur.execute(backup_sql)
    conn.commit()
    print(f"   ✅ Backup restored")
except Exception as e:
    print(f"   ❌ Restore failed: {e}")
    conn.rollback()
    exit(1)

# Verify restoration
cur.execute('SELECT COUNT(*) FROM employee_pay_master WHERE cpp_employee < 0')
negative_count = cur.fetchone()[0]
print(f"   Negative CPP records after restore: {negative_count}")

cur.close()
conn.close()

print("\n✅ Restoration complete. Now run: python scripts/fix_cpp_safe_records.py")
