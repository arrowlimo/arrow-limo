#!/usr/bin/env python3
"""
Backup all tables before schema sync
Creates SQL dumps and JSON backups of the 11 affected tables
"""

import os
import sys
import subprocess
import json
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# Database credentials
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': os.environ.get('DB_PASSWORD', 'ArrowLimousine')
}

# Tables to backup  
TABLES_TO_BACKUP = [
    'accounting_entries',
    'banking_transactions',
    'chart_of_accounts',
    'charter_payments',
    'charter_routes',
    'clients',
    'employees',
    'general_ledger',
    'income_ledger',
    'receipt_categories',
    'run_type_default_charges'
]

def create_directory(path):
    """Create backup directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)

def backup_with_pg_dump(table, backup_dir):
    """Create SQL dump of a table using pg_dump"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'{table}_backup_{timestamp}.sql')
    
    # Set password in environment
    env = os.environ.copy()
    env['PGPASSWORD'] = DB_CONFIG['password']
    
    # Find pg_dump
    pg_dump_paths = [
        r'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe',
        r'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe',
        r'C:\Program Files\PostgreSQL\16\bin\pg_dump.exe',
        r'C:\Program Files\PostgreSQL\15\bin\pg_dump.exe',
    ]
    
    pg_dump = None
    for path in pg_dump_paths:
        if os.path.exists(path):
            pg_dump = path
            break
    
    if not pg_dump:
        print(f"❌ pg_dump not found in standard PostgreSQL paths")
        return None
    
    try:
        cmd = [
            pg_dump,
            '-h', DB_CONFIG['host'],
            '-U', DB_CONFIG['user'],
            '-d', DB_CONFIG['database'],
            '-t', table,
            '--column-inserts',
            '--no-owner',
            '--no-privileges'
        ]
        
        with open(backup_file, 'w') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env, text=True)
        
        if result.returncode == 0:
            file_size = os.path.getsize(backup_file)
            print(f"✅ {table}: {file_size:,} bytes")
            return backup_file
        else:
            print(f"❌ {table}: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ {table}: {e}")
        return None

def backup_with_python(table, backup_dir):
    """Backup table data to JSON using psycopg2"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(backup_dir, f'{table}_backup_{timestamp}.json')
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f'SELECT COUNT(*) as row_count FROM "{table}"')
        row_count = cur.fetchone()['row_count']
        
        cur.execute(f'SELECT * FROM "{table}"')
        rows = cur.fetchall()
        
        backup_data = {
            'table': table,
            'timestamp': datetime.now().isoformat(),
            'row_count': row_count,
            'data': [dict(row) for row in rows]
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        cur.close()
        conn.close()
        
        file_size = os.path.getsize(backup_file)
        print(f"✅ {table}: {row_count:,} rows → {file_size:,} bytes")
        return backup_file
    except Exception as e:
        print(f"❌ {table}: {e}")
        return None

def main():
    """Create backups of all affected tables"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f'l:\\limo\\database_backups\\schema_sync_{timestamp}'
    
    print("=" * 80)
    print(f"DATABASE BACKUP - SCHEMA SYNC PREPARATION")
    print("=" * 80)
    print(f"Backup directory: {backup_dir}")
    print(f"Tables: {len(TABLES_TO_BACKUP)}")
    print()
    
    create_directory(backup_dir)
    
    print("Backing up tables:")
    print("-" * 80)
    
    successful = []
    failed = []
    
    for table in TABLES_TO_BACKUP:
        # Try pg_dump first for SQL format
        sql_backup = backup_with_pg_dump(table, backup_dir)
        # Always do JSON backup for data preservation
        json_backup = backup_with_python(table, backup_dir)
        
        if sql_backup or json_backup:
            successful.append(table)
        else:
            failed.append(table)
    
    print()
    print("=" * 80)
    print("BACKUP SUMMARY")
    print("=" * 80)
    print(f"✅ Successful: {len(successful)}/{len(TABLES_TO_BACKUP)}")
    print(f"❌ Failed: {len(failed)}/{len(TABLES_TO_BACKUP)}")
    print()
    print(f"Backup location: {backup_dir}")
    print()
    
    if failed:
        print("Failed tables:")
        for table in failed:
            print(f"  - {table}")
        return 1
    
    print("✅ All tables backed up successfully!")
    print()
    print("NEXT STEPS:")
    print("1. Review backup files in: " + backup_dir)
    print("2. Execute: l:\\limo\\archive_old_scripts\\old_database_files\\sync_local_database.sql")
    print("3. Verify columns were added")
    print("4. Test application connectivity")
    print()
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
