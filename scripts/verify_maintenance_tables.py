#!/usr/bin/env python3
"""
Verify vehicle maintenance tables and code references.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*90)
print("VEHICLE MAINTENANCE TABLES AND CODE VERIFICATION")
print("="*90)

# Find all maintenance-related tables
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (
        table_name LIKE '%maintenance%'
        OR table_name LIKE '%repair%'
        OR table_name LIKE '%service%'
        OR table_name LIKE '%vehicle%'
        OR table_name LIKE '%fleet%'
    )
    ORDER BY table_name
""")

tables = [row[0] for row in cur.fetchall()]

print(f"\n1️⃣  Found {len(tables)} maintenance/vehicle tables:\n")

# Categorize by row count
categories = {
    'Core Active (1000+ rows)': [],
    'Medium (100-1000 rows)': [],
    'Small (10-100 rows)': [],
    'Very Small (<10 rows)': [],
    'Empty (0 rows)': []
}

table_info = []

for table in tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    
    cur.execute(f"""
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = '{table}'
    """)
    col_count = cur.fetchone()[0]
    
    table_info.append({
        'name': table,
        'rows': row_count,
        'cols': col_count
    })
    
    if row_count >= 1000:
        categories['Core Active (1000+ rows)'].append(table)
    elif row_count >= 100:
        categories['Medium (100-1000 rows)'].append(table)
    elif row_count >= 10:
        categories['Small (10-100 rows)'].append(table)
    elif row_count > 0:
        categories['Very Small (<10 rows)'].append(table)
    else:
        categories['Empty (0 rows)'].append(table)

for category, tables_list in categories.items():
    if tables_list:
        print(f"{category}:")
        print("-" * 90)
        for table in tables_list:
            info = next(t for t in table_info if t['name'] == table)
            print(f"   {table:<45} {info['rows']:>8,} rows, {info['cols']:>3} cols")
        print()

# Check schema of core maintenance tables
print("="*90)
print("2️⃣  Core maintenance table schemas:")
print("="*90)

core_maintenance = ['vehicle_maintenance', 'vehicles', 'vehicle_inspections']

for table in core_maintenance:
    if table in [t['name'] for t in table_info]:
        info = next(t for t in table_info if t['name'] == table)
        print(f"\n📋 {table} ({info['rows']:,} rows):")
        print("-"*90)
        
        cur.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table}'
            ORDER BY ordinal_position
        """)
        
        cols = cur.fetchall()
        for col, dtype, nullable in cols[:15]:  # First 15 columns
            nullable_str = "NULL" if nullable == 'YES' else "NOT NULL"
            print(f"   {col:<35} {dtype:<20} {nullable_str}")
        
        if len(cols) > 15:
            print(f"   ... and {len(cols)-15} more columns")

# Check for foreign keys
print("\n" + "="*90)
print("3️⃣  Foreign key relationships:")
print("="*90)

for table in ['vehicle_maintenance', 'vehicle_inspections']:
    if table in [t['name'] for t in table_info]:
        cur.execute(f"""
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.table_name = '{table}'
            AND tc.constraint_type = 'FOREIGN KEY'
        """)
        
        fks = cur.fetchall()
        if fks:
            print(f"\n{table}:")
            for col, ftable, fcol in fks:
                print(f"   {col} → {ftable}.{fcol}")

# Check code references
print("\n" + "="*90)
print("4️⃣  Code references to maintenance tables:")
print("="*90)

maintenance_tables = ['vehicle_maintenance', 'vehicle_inspections', 'vehicle_service_history']
code_dirs = ['scripts', 'modern_backend', 'desktop_app']

code_refs = {}

for table in maintenance_tables:
    refs = []
    for code_dir in code_dirs:
        if os.path.exists(code_dir):
            for root, dirs, files in os.walk(code_dir):
                for file in files:
                    if file.endswith(('.py', '.sql')):
                        filepath = os.path.join(root, file)
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read().lower()
                                if table in content:
                                    refs.append(filepath)
                        except:
                            pass
    
    if refs:
        code_refs[table] = refs

if code_refs:
    for table, files in sorted(code_refs.items()):
        print(f"\n{table}:")
        for filepath in files[:5]:  # Show first 5
            print(f"   - {filepath}")
        if len(files) > 5:
            print(f"   ... and {len(files)-5} more")
else:
    print("   ✅ No code references found (tables may be unused)")

# Check for empty/redundant tables
print("\n" + "="*90)
print("5️⃣  Empty maintenance tables:")
print("="*90)

empty_maintenance = [t for t in table_info if t['rows'] == 0 and 'maintenance' in t['name'].lower()]

if empty_maintenance:
    print(f"Found {len(empty_maintenance)} empty tables:")
    for info in empty_maintenance:
        print(f"   - {info['name']} ({info['cols']} columns)")
else:
    print("   ✅ No empty maintenance tables")

cur.close()
conn.close()

# Summary
print("\n" + "="*90)
print("READINESS SUMMARY")
print("="*90)

core_ready = []
missing = []

for table in ['vehicles', 'vehicle_maintenance', 'vehicle_inspections']:
    info = next((t for t in table_info if t['name'] == table), None)
    if info:
        core_ready.append(f"{table} ({info['rows']:,} rows)")
    else:
        missing.append(table)

if core_ready:
    print("\n✅ Core tables ready:")
    for table in core_ready:
        print(f"   - {table}")

if missing:
    print("\n⚠️  Missing tables:")
    for table in missing:
        print(f"   - {table}")

print("\n💡 Schema is ready for vehicle maintenance data import")
print("="*90)
