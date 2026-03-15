#!/usr/bin/env python3
"""
Export beverage-related tables from local PostgreSQL to SQL dump files
that can be imported into Neon.
"""
import subprocess
import os

# Beverage-related tables to export
BEVERAGE_TABLES = [
    'beverage_orders',
    'beverage_order_items', 
    'beverage_products',
    'beverage_menu',
    'beverage_cart',
    'beverages',
    'charter_beverages',
    'charter_beverage_items',
    'charter_beverage_orders',
]

# Export directory
EXPORT_DIR = 'l:/limo/neon_exports'
os.makedirs(EXPORT_DIR, exist_ok=True)

print("=" * 80)
print("EXPORTING BEVERAGE TABLES FROM LOCAL POSTGRESQL")
print("=" * 80)

# Database connection settings
DB_HOST = 'localhost'
DB_NAME = 'almsdata'
DB_USER = 'postgres'

for table in BEVERAGE_TABLES:
    output_file = os.path.join(EXPORT_DIR, f'{table}.sql')
    
    print(f"\nExporting {table}...")
    
    # Use pg_dump to export schema and data
    cmd = [
        'pg_dump',
        '-h', DB_HOST,
        '-U', DB_USER,
        '-d', DB_NAME,
        '-t', table,
        '--clean',  # Add DROP TABLE IF EXISTS
        '--if-exists',  # Use IF EXISTS in DROP statements
        '--no-owner',  # Don't include ownership commands
        '--no-privileges',  # Don't include privilege commands
        '-f', output_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Check file size
        size = os.path.getsize(output_file)
        print(f"  ✅ Exported to {output_file} ({size:,} bytes)")
        
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Error exporting {table}: {e.stderr}")
        continue

print("\n" + "=" * 80)
print("EXPORT COMPLETE")
print("=" * 80)
print(f"\nFiles saved to: {EXPORT_DIR}")
print("\nTo import to Neon:")
print("1. Set NEON_PASSWORD environment variable")
print("2. Run: python import_to_neon.py")
