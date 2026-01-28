#!/usr/bin/env python
# -*- coding: utf-8 -*-
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

legacy_tables = ['limo_clients', 'limo_clients_clean', 'limo_contacts', 'lms_charges', 'lms_customers_enhanced', 'lms_deposits']

print("="*80)
print("LEGACY TABLE DEPENDENCY ANALYSIS")
print("="*80)

# Check for foreign keys pointing FROM other tables TO these legacy tables
print("\n1. FOREIGN KEY DEPENDENCIES (incoming):")
print("-" * 80)
any_deps = False
for table in legacy_tables:
    cur.execute("""
        SELECT kcu.constraint_name, ccu.table_schema, kcu.table_name, kcu.column_name, ccu.table_name as referenced_table, ccu.column_name as referenced_column
        FROM information_schema.constraint_column_usage ccu
        JOIN information_schema.key_column_usage kcu ON ccu.constraint_name = kcu.constraint_name
        WHERE ccu.table_name = %s
          AND ccu.constraint_name LIKE '%%fkey'
    """, (table,))
    fk = cur.fetchall()
    if fk:
        any_deps = True
        print(f"\n❌ {table} IS REFERENCED BY:")
        for row in fk:
            print(f"   {row[2]}.{row[3]} → {row[4]}.{row[5]}")
    else:
        print(f"✅ {table}: no incoming FKs")

if not any_deps:
    print("\n✅ SAFE: No foreign key constraints point to these tables")

# Check for views that depend on these tables
print("\n2. VIEW DEPENDENCIES:")
print("-" * 80)
cur.execute("""
    SELECT table_name, view_definition
    FROM information_schema.views
    WHERE table_schema = 'public'
""")
views = cur.fetchall()
view_deps = []
for view_name, defn in views:
    for table in legacy_tables:
        if table.lower() in defn.lower():
            view_deps.append((view_name, table))
            print(f"⚠️  View '{view_name}' references {table}")

if not view_deps:
    print("✅ SAFE: No views reference these tables")

# Check application code
print("\n3. CODE REFERENCES:")
print("-" * 80)
print("(Must check manually in codebase)")

cur.close()
conn.close()

print("\n" + "="*80)
if not any_deps and not view_deps:
    print("✅ CONCLUSION: Tables are SAFE TO DROP (no DB dependencies)")
    print("   - No foreign keys point to them")
    print("   - No views depend on them")
    print("   - Recommend checking application code for any references")
else:
    print("❌ CANNOT DROP: Dependencies exist")
print("="*80)
