#!/usr/bin/env python3
import psycopg2
import os
from datetime import datetime
import subprocess

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = f"L:\\limo\\almsdata_backup_{timestamp}.sql"

print(f"Starting database backup at {datetime.now().isoformat()}")
print(f"Backup file: {backup_file}")

try:
    # Try using pg_dump if available
    result = subprocess.run([
        'pg_dump',
        '-h', 'localhost',
        '-U', 'postgres',
        '-d', 'almsdata',
        '-f', backup_file
    ], capture_output=True, text=True, timeout=300)
    
    if result.returncode == 0:
        file_size = os.path.getsize(backup_file)
        print(f"✅ Backup completed successfully: {file_size:,} bytes")
    else:
        print(f"❌ Backup failed: {result.stderr}")
        
except Exception as e:
    print(f"❌ Error: {e}")
