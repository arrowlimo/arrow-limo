#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1.2-1.4: Drop limo_contacts, lms_charges, lms_deposits safely.
Verify no dependencies, then drop.
"""
import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

tables_to_drop = ['limo_contacts', 'lms_charges', 'lms_deposits']

print("="*80)
print("PHASE 1.2-1.4: DROP LEGACY TABLES")
print("="*80)

for table in tables_to_drop:
    print(f"\n📋 {table}:")
    
    # Check for FK references
    cur.execute("""
        SELECT kcu.constraint_name, ccu.table_schema, kcu.table_name, kcu.column_name
        FROM information_schema.constraint_column_usage ccu
        JOIN information_schema.key_column_usage kcu ON ccu.constraint_name = kcu.constraint_name
        WHERE ccu.table_name = %s
          AND ccu.constraint_name LIKE '%%fkey'
    """, (table,))
    fks = cur.fetchall()
    
    if fks:
        print(f"   ❌ Cannot drop: Foreign keys exist")
        for fk in fks:
            print(f"      {fk[2]}.{fk[3]} → {table}")
        continue
    
    # Check for view references
    cur.execute("""
        SELECT table_name, view_definition
        FROM information_schema.views
        WHERE table_schema = 'public'
    """)
    views = cur.fetchall()
    view_refs = []
    for view_name, defn in views:
        if table.lower() in defn.lower():
            view_refs.append(view_name)
    
    if view_refs:
        print(f"   ❌ Cannot drop: Views reference this table")
        for view in view_refs:
            print(f"      {view}")
        continue
    
    # Safe to drop
    print(f"   ✅ No dependencies found. Dropping...")
    try:
        cur.execute(f"DROP TABLE {table} CASCADE")
        conn.commit()
        print(f"   ✅ DROPPED: {table}")
    except Exception as e:
        conn.rollback()
        print(f"   ❌ ERROR: {e}")

cur.close()
conn.close()

print("\n" + "="*80)
print("✅ Phase 1 deletions complete")
print("="*80)
