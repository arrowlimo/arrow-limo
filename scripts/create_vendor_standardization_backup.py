#!/usr/bin/env python3
"""
Create database backup after vendor standardization.
"""

import subprocess
import os
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = f"l:\\limo\\almsdata_backup_VENDOR_STANDARDIZATION_{timestamp}.sql"

print("=" * 80)
print("DATABASE BACKUP")
print("=" * 80)
print(f"\nBackup file: {backup_file}")

# Use full path to pg_dump
pg_dump_path = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"

if not os.path.exists(pg_dump_path):
    # Try version 17
    pg_dump_path = r"C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"

if not os.path.exists(pg_dump_path):
    # Try version 16
    pg_dump_path = r"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe"
    
if not os.path.exists(pg_dump_path):
    # Try version 15
    pg_dump_path = r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe"

if not os.path.exists(pg_dump_path):
    print(f"❌ pg_dump not found in standard PostgreSQL directories")
    exit(1)

print(f"Using: {pg_dump_path}")

# Set password environment variable
os.environ['PGPASSWORD'] = '***REDACTED***'

# Run pg_dump
cmd = [
    pg_dump_path,
    '-h', 'localhost',
    '-U', 'postgres',
    '-d', 'almsdata',
    '-f', backup_file
]

print("\nCreating backup...")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode == 0:
    size_mb = os.path.getsize(backup_file) / (1024 * 1024)
    print(f"✅ BACKUP COMPLETE: {size_mb:.2f} MB")
    print(f"   Location: {backup_file}")
else:
    print(f"❌ BACKUP FAILED")
    if result.stderr:
        print(f"   Error: {result.stderr}")
