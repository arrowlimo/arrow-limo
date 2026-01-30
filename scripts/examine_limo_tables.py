#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Summary of remaining LIMO tables: row counts, column counts, and key data samples.
"""
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

limo_tables = ['limo_addresses', 'limo_addresses_clean', 'limo_clients', 'limo_clients_clean']

print("="*80)
print("REMAINING LIMO TABLES - DATA OVERVIEW")
print("="*80)

for table in limo_tables:
    print(f"\n📊 {table.upper()}")
    print("-" * 80)
    
    # Row count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"Records: {count:,}")
    
    # Column count & list
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table,))
    cols = cur.fetchall()
    print(f"Columns: {len(cols)}")
    for col_name, dtype in cols[:8]:  # Show first 8 columns
        print(f"  - {col_name:<30} {dtype}")
    if len(cols) > 8:
        print(f"  ... and {len(cols) - 8} more columns")
    
    # Sample data
    if count > 0:
        print(f"\nSample records (first 3):")
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        sample = cur.fetchall()
        for i, row in enumerate(sample, 1):
            col_vals = list(row)[:3]  # Show first 3 column values
            print(f"  Row {i}: {col_vals}")

# Check relationships
print("\n" + "="*80)
print("RELATIONSHIPS & DEPENDENCIES")
print("="*80)

# FK dependencies
print("\nForeign Key Relationships:")
print("-" * 80)

for table in limo_tables:
    cur.execute("""
        SELECT kcu.constraint_name, ccu.table_name as referenced_table, ccu.column_name as referenced_column
        FROM information_schema.constraint_column_usage ccu
        JOIN information_schema.key_column_usage kcu ON ccu.constraint_name = kcu.constraint_name
        WHERE ccu.table_name = %s
          AND ccu.constraint_name LIKE '%%fkey'
    """, (table,))
    fks = cur.fetchall()
    
    if fks:
        print(f"\n{table} IS REFERENCED BY:")
        for constraint, ref_table, ref_col in fks:
            print(f"  {ref_table} → {table}")
    else:
        print(f"\n{table}: No incoming FKs")

# View dependencies
print("\n\nView Dependencies:")
print("-" * 80)

cur.execute("""
    SELECT table_name, view_definition
    FROM information_schema.views
    WHERE table_schema = 'public'
""")
views = cur.fetchall()

view_deps = {}
for table in limo_tables:
    view_deps[table] = []
    for view_name, defn in views:
        if table.lower() in defn.lower():
            view_deps[table].append(view_name)

for table, view_list in view_deps.items():
    if view_list:
        print(f"\n{table} used by {len(view_list)} views:")
        for view in view_list[:5]:
            print(f"  - {view}")
        if len(view_list) > 5:
            print(f"  ... and {len(view_list) - 5} more")
    else:
        print(f"\n{table}: No views")

cur.close()
conn.close()
