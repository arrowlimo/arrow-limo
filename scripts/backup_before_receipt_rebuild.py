#!/usr/bin/env python3
"""Create backup before receipt rebuild."""
import subprocess
import os
from datetime import datetime

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = f"L:\\limo\\almsdata_backup_BEFORE_RECEIPT_REBUILD_{timestamp}.sql"

print(f"Creating backup: {backup_file}")
print("This may take a few minutes...")

# Use pg_dump via Python
result = subprocess.run([
    "C:\\Program Files\\PostgreSQL\\16\\bin\\pg_dump.exe",
    "-h", "localhost",
    "-U", "postgres",
    "-d", "almsdata",
    "-f", backup_file
], env={**os.environ, 'PGPASSWORD': '***REMOVED***'}, capture_output=True, text=True)

if result.returncode == 0:
    size = os.path.getsize(backup_file) / (1024*1024)
    print(f"✅ Backup created successfully: {size:.1f} MB")
    print(f"   Location: {backup_file}")
else:
    print(f"❌ Backup failed!")
    print(f"Error: {result.stderr}")
    exit(1)
