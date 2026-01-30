#!/usr/bin/env python3
"""
Clean up empty staging tables and analyze naming consistency issues.
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print(f"\n{'='*80}")
print("PART 1: EMPTY STAGING TABLES CLEANUP")
print(f"{'='*80}\n")

# Find empty staging/import tables
cur.execute("""
    SELECT t.table_name,
           pg_size_pretty(pg_total_relation_size(quote_ident(t.table_name))) as size
    FROM information_schema.tables t
    WHERE t.table_schema = 'public'
      AND t.table_type = 'BASE TABLE'
      AND (t.table_name LIKE '%staging%' 
        OR t.table_name LIKE '%import%'
        OR t.table_name LIKE '%temp%')
    ORDER BY t.table_name
""")

staging_tables = cur.fetchall()
empty_tables = []

for table, size in staging_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    
    if row_count == 0:
        # Check for FK references
        cur.execute("""
            SELECT COUNT(*)
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu 
              ON tc.constraint_name = ccu.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_name = %s
        """, (table,))
        fk_refs = cur.fetchone()[0]
        
        empty_tables.append((table, size, fk_refs))

print(f"Empty staging tables found: {len(empty_tables)}\n")
print(f"{'Table Name':<50} {'Size':<12} {'FK Refs'}")
print("-" * 75)
for table, size, fk_refs in empty_tables:
    safe = "✅ SAFE" if fk_refs == 0 else f"⚠️ {fk_refs} refs"
    print(f"{table:<50} {size:<12} {safe}")

safe_to_drop = [t for t, _, refs in empty_tables if refs == 0]

print(f"\n{'='*80}")
print("PART 2: PRIMARY KEY NAMING CONSISTENCY")
print(f"{'='*80}\n")

# Find tables with generic 'id' instead of 'table_id'
cur.execute("""
    SELECT t.table_name, c.column_name
    FROM information_schema.tables t
    JOIN information_schema.columns c ON t.table_name = c.table_name
    WHERE t.table_schema = 'public'
      AND t.table_type = 'BASE TABLE'
      AND c.column_name = 'id'
      AND c.ordinal_position = 1
    ORDER BY t.table_name
""")

generic_id_tables = cur.fetchall()

print(f"Tables using generic 'id' (should be 'table_id'): {len(generic_id_tables)}\n")

# Group by prefix
from collections import defaultdict
by_prefix = defaultdict(list)
for table, col in generic_id_tables[:20]:  # Show first 20
    by_prefix[table.split('_')[0]].append(table)

print("Sample tables (first 20):")
for table, col in generic_id_tables[:20]:
    print(f"  {table:<40} → Should be: {table}_id")

# Find inconsistent PK naming (where PK doesn't match table_name + '_id')
print(f"\n{'='*80}")
print("INCONSISTENT PRIMARY KEY NAMES")
print(f"{'='*80}\n")

cur.execute("""
    SELECT 
        tc.table_name,
        kcu.column_name as pk_column,
        tc.table_name || '_id' as expected_name,
        CASE 
            WHEN kcu.column_name = tc.table_name || '_id' THEN '✅'
            WHEN kcu.column_name = 'id' THEN '⚠️ Generic'
            ELSE '❌ Non-standard'
        END as status
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu 
        ON tc.constraint_name = kcu.constraint_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = 'public'
      AND kcu.column_name != tc.table_name || '_id'
    ORDER BY status DESC, tc.table_name
    LIMIT 30
""")

print(f"{'Table':<35} {'Current PK':<25} {'Expected':<25} {'Status'}")
print("-" * 100)
for row in cur.fetchall():
    table, pk, expected, status = row
    print(f"{table:<35} {pk:<25} {expected:<25} {status}")

# Summary
print(f"\n{'='*80}")
print("CLEANUP RECOMMENDATIONS")
print(f"{'='*80}\n")

print(f"1. SAFE TO DROP ({len(safe_to_drop)} empty staging tables):")
for table in safe_to_drop[:10]:
    print(f"   DROP TABLE IF EXISTS {table} CASCADE;")
if len(safe_to_drop) > 10:
    print(f"   ... and {len(safe_to_drop) - 10} more")

print(f"\n2. PRIMARY KEY NAMING:")
print(f"   - {len(generic_id_tables)} tables use generic 'id'")
print(f"   - Standardizing would require:")
print(f"     • ALTER TABLE ... RENAME COLUMN id TO table_id")
print(f"     • Update all foreign key references")
print(f"     • Update application code")
print(f"   - RECOMMENDATION: Leave as-is unless breaking changes acceptable")

cur.close()
conn.close()
