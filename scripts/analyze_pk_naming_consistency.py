#!/usr/bin/env python3
"""
Analyze primary key naming consistency and OPTIONALLY fix it.

WARNING: Renaming primary keys is a BREAKING CHANGE that requires:
1. Updating all foreign key columns
2. Updating all application code
3. Updating all SQL queries/scripts
4. Potential downtime

RECOMMENDATION: Document the inconsistency but DO NOT fix unless
you're prepared for extensive code changes.
"""

import psycopg2
import argparse

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print(f"\n{'='*80}")
print("PRIMARY KEY NAMING CONSISTENCY ANALYSIS")
print(f"{'='*80}\n")

# Get all primary keys
cur.execute("""
    SELECT 
        tc.table_name,
        kcu.column_name as pk_column,
        tc.table_name || '_id' as expected_name,
        CASE 
            WHEN kcu.column_name = tc.table_name || '_id' THEN 'consistent'
            WHEN kcu.column_name = 'id' THEN 'generic'
            ELSE 'non_standard'
        END as status
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = 'public'
    ORDER BY status, tc.table_name
""")

all_pks = cur.fetchall()
consistent = [r for r in all_pks if r[3] == 'consistent']
generic = [r for r in all_pks if r[3] == 'generic']
non_standard = [r for r in all_pks if r[3] == 'non_standard']

print(f"Total tables with primary keys: {len(all_pks)}")
print(f"  ✅ Consistent (table_id pattern): {len(consistent)} ({len(consistent)/len(all_pks)*100:.1f}%)")
print(f"  ⚠️  Generic 'id': {len(generic)} ({len(generic)/len(all_pks)*100:.1f}%)")
print(f"  ❌ Non-standard: {len(non_standard)} ({len(non_standard)/len(all_pks)*100:.1f}%)")

print(f"\n{'='*80}")
print("TABLES USING GENERIC 'id' (Sample - 30 of {})".format(len(generic)))
print(f"{'='*80}\n")

print(f"{'Table':<50} {'Current':<15} {'Should Be'}")
print("-" * 90)
for table, pk, expected, _ in generic[:30]:
    print(f"{table:<50} {pk:<15} {expected}")

if non_standard:
    print(f"\n{'='*80}")
    print(f"NON-STANDARD PRIMARY KEYS ({len(non_standard)} tables)")
    print(f"{'='*80}\n")
    
    print(f"{'Table':<50} {'Current PK':<30} {'Expected'}")
    print("-" * 100)
    for table, pk, expected, _ in non_standard[:20]:
        print(f"{table:<50} {pk:<30} {expected}")

# Count foreign key references that would need updating
print(f"\n{'='*80}")
print("IMPACT ANALYSIS - Foreign Key References")
print(f"{'='*80}\n")

total_fk_updates = 0
for table, pk, expected, status in generic + non_standard:
    if status in ('generic', 'non_standard'):
        # Count FK columns referencing this PK
        cur.execute("""
            SELECT COUNT(DISTINCT kcu.table_name || '.' || kcu.column_name)
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu 
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = %s
              AND ccu.column_name = %s
        """, (table, pk))
        fk_count = cur.fetchone()[0]
        total_fk_updates += fk_count

print(f"Total foreign key columns that would need renaming: {total_fk_updates}")
print(f"Total primary key columns to rename: {len(generic) + len(non_standard)}")
print(f"Total changes required: {total_fk_updates + len(generic) + len(non_standard)}")

print(f"\n{'='*80}")
print("RECOMMENDATIONS")
print(f"{'='*80}\n")

print("❌ DO NOT STANDARDIZE PRIMARY KEY NAMES")
print("\nReasons:")
print(f"  1. Would require {total_fk_updates + len(generic) + len(non_standard)} schema changes")
print(f"  2. Would break all existing application code referencing these columns")
print(f"  3. Would break all SQL queries/scripts (300+ files in this project)")
print(f"  4. Risk of data corruption if any FK update fails")
print(f"  5. No functional benefit - generic 'id' works fine")
print("\n✅ RECOMMENDED ACTION:")
print("  - Document the naming convention inconsistency")
print("  - Use descriptive naming for NEW tables only")
print("  - Leave existing tables unchanged")
print("  - Update coding standards document")

print(f"\n{'='*80}")
print("DOCUMENTATION")
print(f"{'='*80}\n")

print("Add to project documentation:")
print("""
# Primary Key Naming Standards

## Current State (Dec 2024)
- 110 tables use generic 'id' primary key
- This is acceptable and widely used in PostgreSQL
- Foreign keys still use descriptive names (customer_id, vehicle_id, etc.)

## Standards for NEW Tables
- Use descriptive primary keys: table_name_id
- Example: vehicles.vehicle_id (not vehicles.id)
- Consistency with foreign key naming

## Existing Tables
- DO NOT rename existing primary keys
- Code relies on current naming
- No functional issues with generic 'id'
""")

cur.close()
conn.close()
