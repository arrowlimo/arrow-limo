#!/usr/bin/env python3
"""
Import beverage tables to Neon cloud database.
Reads SQL dumps created by export_beverage_tables.py
"""
import os
import subprocess

# Neon connection settings - update these
NEON_HOST = 'ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech'
NEON_DB = 'neondb'
NEON_USER = 'neondb_owner'
NEON_PASSWORD = os.environ.get('NEON_PASSWORD', '')  # Set via environment variable

if not NEON_PASSWORD:
    print("❌ ERROR: NEON_PASSWORD environment variable not set")
    print("\nSet it with:")
    print("  $env:NEON_PASSWORD='your_password_here'  # PowerShell")
    print("  export NEON_PASSWORD='your_password_here'  # Bash")
    exit(1)

# Import directory
IMPORT_DIR = 'l:/limo/neon_exports'

# List SQL files
sql_files = [f for f in os.listdir(IMPORT_DIR) if f.endswith('.sql')]

if not sql_files:
    print(f"❌ No SQL files found in {IMPORT_DIR}")
    exit(1)

print("=" * 80)
print("IMPORTING BEVERAGE TABLES TO NEON")
print("=" * 80)
print(f"\nTarget: {NEON_HOST}")
print(f"Database: {NEON_DB}")
print(f"User: {NEON_USER}")
print(f"\nFound {len(sql_files)} SQL files to import\n")

# Set password environment variable for psql
env = os.environ.copy()
env['PGPASSWORD'] = NEON_PASSWORD

for sql_file in sorted(sql_files):
    file_path = os.path.join(IMPORT_DIR, sql_file)
    table_name = sql_file.replace('.sql', '')
    
    print(f"Importing {table_name}...")
    
    # Use psql to import
    cmd = [
        'psql',
        '-h', NEON_HOST,
        '-U', NEON_USER,
        '-d', NEON_DB,
        '-f', file_path,
        '--set', 'sslmode=require',
        '--quiet',  # Suppress messages
    ]
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        print(f"  ✅ Imported {table_name}")
        
        if result.stderr and 'ERROR' in result.stderr:
            print(f"     Warning: {result.stderr.strip()}")
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error importing {table_name}:")
        print(f"     {e.stderr.strip()}")
        
        # Ask whether to continue
        response = input("\nContinue with remaining tables? (y/n): ")
        if response.lower() != 'y':
            print("\nImport cancelled.")
            exit(1)

print("\n" + "=" * 80)
print("IMPORT COMPLETE")
print("=" * 80)
print("\nVerify the import:")
print(f"  psql -h {NEON_HOST} -U {NEON_USER} -d {NEON_DB}")
print(f"  \\dt beverage*")
