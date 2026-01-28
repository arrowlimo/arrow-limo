"""
Analyze Database Tables - Identify Unused, Duplicate, and Error Tables
=======================================================================

Purpose: 
- Identify tables with no data (empty)
- Find duplicate/redundant tables
- Detect tables that serve no purpose
- Preserve staging tables for ETL processes
- Recommend tables safe to drop

Strategy:
1. Get all table names and row counts
2. Check for duplicate schemas (same columns)
3. Analyze naming patterns for redundancy
4. Check last access/modification dates
5. Identify orphaned tables (no foreign key relationships)
6. Review staging vs production tables
"""

import psycopg2
from collections import defaultdict
import json

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

def get_all_tables():
    """Get all tables with row counts and sizes."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
            pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
    """)
    
    tables = cur.fetchall()
    
    # Get row counts for each table
    table_info = []
    for schema, table, size, size_bytes in tables:
        try:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            row_count = cur.fetchone()[0]
        except Exception as e:
            row_count = -1  # Error accessing table
        
        table_info.append({
            'schema': schema,
            'name': table,
            'size': size,
            'size_bytes': size_bytes,
            'row_count': row_count
        })
    
    cur.close()
    conn.close()
    return table_info

def get_table_columns(table_name):
    """Get column information for a table."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length
        FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    
    columns = cur.fetchall()
    cur.close()
    conn.close()
    
    return [(col[0], col[1]) for col in columns]

def get_foreign_keys():
    """Get all foreign key relationships."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
    """)
    
    fks = cur.fetchall()
    cur.close()
    conn.close()
    
    return fks

def categorize_tables(tables):
    """Categorize tables by purpose/naming pattern."""
    categories = {
        'staging': [],
        'temp': [],
        'backup': [],
        'import': [],
        'legacy': [],
        'archive': [],
        'test': [],
        'empty': [],
        'small': [],
        'views_backing': [],
        'core': []
    }
    
    for table in tables:
        name = table['name'].lower()
        row_count = table['row_count']
        
        # Categorize by name patterns
        if 'staging' in name or '_stg' in name or 'stage' in name:
            categories['staging'].append(table)
        elif 'temp' in name or '_tmp' in name or name.startswith('tmp_'):
            categories['temp'].append(table)
        elif 'backup' in name or '_bak' in name or name.endswith('_backup'):
            categories['backup'].append(table)
        elif 'import' in name or '_imp' in name:
            categories['import'].append(table)
        elif 'legacy' in name or '_old' in name or 'deprecated' in name:
            categories['legacy'].append(table)
        elif 'archive' in name or '_arch' in name:
            categories['archive'].append(table)
        elif 'test' in name or '_test' in name or name.startswith('test_'):
            categories['test'].append(table)
        elif row_count == 0:
            categories['empty'].append(table)
        elif row_count > 0 and row_count < 10:
            categories['small'].append(table)
        else:
            categories['core'].append(table)
    
    return categories

def find_duplicate_schemas(tables):
    """Find tables with identical column structures."""
    conn = psycopg2.connect(**DB_CONFIG)
    
    # Get columns for each table
    table_schemas = {}
    for table in tables:
        cols = get_table_columns(table['name'])
        schema_sig = tuple(sorted(cols))
        
        if schema_sig not in table_schemas:
            table_schemas[schema_sig] = []
        table_schemas[schema_sig].append(table)
    
    # Find duplicates
    duplicates = {}
    for schema_sig, table_list in table_schemas.items():
        if len(table_list) > 1:
            # Multiple tables with same schema
            duplicates[str(schema_sig[:3]) + '...'] = table_list
    
    conn.close()
    return duplicates

def analyze_table_relationships():
    """Analyze which tables have no relationships."""
    fks = get_foreign_keys()
    
    # Tables that reference others
    referencing_tables = set(fk[0] for fk in fks)
    # Tables that are referenced
    referenced_tables = set(fk[2] for fk in fks)
    
    # Tables in relationships
    connected_tables = referencing_tables | referenced_tables
    
    return {
        'referencing': referencing_tables,
        'referenced': referenced_tables,
        'connected': connected_tables
    }

def generate_report(tables):
    """Generate comprehensive analysis report."""
    print("=" * 80)
    print("DATABASE TABLE ANALYSIS - UNUSED & ERROR TABLES")
    print("=" * 80)
    print(f"\nTotal Tables: {len(tables)}")
    print(f"Total Database Size: {sum(t['size_bytes'] for t in tables) / 1024 / 1024 / 1024:.2f} GB")
    
    # Categorize tables
    print("\n" + "=" * 80)
    print("TABLE CATEGORIZATION")
    print("=" * 80)
    
    categories = categorize_tables(tables)
    
    for category, table_list in categories.items():
        if table_list:
            print(f"\n{category.upper().replace('_', ' ')} ({len(table_list)} tables):")
            print("-" * 80)
            for table in sorted(table_list, key=lambda x: x['row_count'], reverse=True):
                status = "[WARN] EMPTY" if table['row_count'] == 0 else "✓"
                print(f"  {status} {table['name']:<50} {table['row_count']:>10,} rows  {table['size']:>12}")
    
    # Find duplicates
    print("\n" + "=" * 80)
    print("DUPLICATE SCHEMA DETECTION")
    print("=" * 80)
    
    duplicates = find_duplicate_schemas(tables)
    if duplicates:
        for i, (schema_sig, table_list) in enumerate(duplicates.items(), 1):
            print(f"\nDuplicate Group {i}:")
            print(f"  Tables with identical schemas: {len(table_list)}")
            for table in table_list:
                print(f"    - {table['name']:<50} {table['row_count']:>10,} rows  {table['size']:>12}")
    else:
        print("  No tables with identical schemas found.")
    
    # Relationship analysis
    print("\n" + "=" * 80)
    print("RELATIONSHIP ANALYSIS")
    print("=" * 80)
    
    relationships = analyze_table_relationships()
    orphaned_tables = [t for t in tables if t['name'] not in relationships['connected']]
    
    print(f"\nTables with foreign key relationships: {len(relationships['connected'])}")
    print(f"Orphaned tables (no relationships): {len(orphaned_tables)}")
    
    if orphaned_tables:
        print("\nOrphaned tables:")
        for table in sorted(orphaned_tables, key=lambda x: x['size_bytes'], reverse=True):
            if table['row_count'] > 0:  # Only show non-empty orphans
                print(f"  - {table['name']:<50} {table['row_count']:>10,} rows  {table['size']:>12}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS FOR CLEANUP")
    print("=" * 80)
    
    # Empty tables
    empty_tables = [t for t in tables if t['row_count'] == 0]
    if empty_tables:
        print(f"\n🗑️  SAFE TO DROP - Empty Tables ({len(empty_tables)}):")
        for table in sorted(empty_tables, key=lambda x: x['name']):
            print(f"  DROP TABLE IF EXISTS {table['name']};")
    
    # Temp tables
    temp_tables = categories['temp']
    if temp_tables:
        print(f"\n🗑️  LIKELY SAFE TO DROP - Temp Tables ({len(temp_tables)}):")
        for table in temp_tables:
            print(f"  DROP TABLE IF EXISTS {table['name']};  -- {table['row_count']:,} rows")
    
    # Test tables
    test_tables = categories['test']
    if test_tables:
        print(f"\n🗑️  LIKELY SAFE TO DROP - Test Tables ({len(test_tables)}):")
        for table in test_tables:
            print(f"  DROP TABLE IF EXISTS {table['name']};  -- {table['row_count']:,} rows")
    
    # Backup tables
    backup_tables = categories['backup']
    if backup_tables:
        print(f"\n[WARN]  REVIEW BEFORE DROP - Backup Tables ({len(backup_tables)}):")
        print("  (Verify data is backed up elsewhere before dropping)")
        for table in backup_tables:
            print(f"  DROP TABLE IF EXISTS {table['name']};  -- {table['row_count']:,} rows")
    
    # Legacy tables
    legacy_tables = categories['legacy']
    if legacy_tables:
        print(f"\n[WARN]  REVIEW BEFORE DROP - Legacy Tables ({len(legacy_tables)}):")
        for table in legacy_tables:
            print(f"  DROP TABLE IF EXISTS {table['name']};  -- {table['row_count']:,} rows")
    
    # Small orphaned tables
    small_orphans = [t for t in orphaned_tables if 0 < t['row_count'] < 100 and t['name'] not in [c['name'] for cat in [categories['staging'], categories['core']] for c in cat]]
    if small_orphans:
        print(f"\n[WARN]  REVIEW - Small Orphaned Tables ({len(small_orphans)}):")
        print("  (No foreign keys, < 100 rows - may be lookup/config tables)")
        for table in small_orphans:
            print(f"  -- {table['name']:<50} {table['row_count']:>5,} rows  {table['size']:>12}")
    
    # Staging tables (preserve)
    staging_tables = categories['staging']
    if staging_tables:
        print(f"\n[OK] PRESERVE - Staging Tables ({len(staging_tables)}):")
        print("  (Keep for ETL processes)")
        for table in staging_tables:
            print(f"  -- {table['name']:<50} {table['row_count']:>10,} rows  {table['size']:>12}")
    
    # Generate SQL cleanup script
    print("\n" + "=" * 80)
    print("GENERATING CLEANUP SCRIPT")
    print("=" * 80)
    
    cleanup_sql = []
    cleanup_sql.append("-- Database Cleanup Script")
    from datetime import datetime
    cleanup_sql.append("-- Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    cleanup_sql.append("-- Review each DROP statement before executing!")
    cleanup_sql.append("")
    cleanup_sql.append("-- Empty Tables (Safe to drop)")
    for table in empty_tables:
        cleanup_sql.append(f"DROP TABLE IF EXISTS {table['name']} CASCADE;  -- 0 rows")
    
    cleanup_sql.append("")
    cleanup_sql.append("-- Temp Tables")
    for table in temp_tables:
        cleanup_sql.append(f"DROP TABLE IF EXISTS {table['name']} CASCADE;  -- {table['row_count']:,} rows")
    
    cleanup_sql.append("")
    cleanup_sql.append("-- Test Tables")
    for table in test_tables:
        cleanup_sql.append(f"DROP TABLE IF EXISTS {table['name']} CASCADE;  -- {table['row_count']:,} rows")
    
    cleanup_sql.append("")
    cleanup_sql.append("-- Backup Tables (REVIEW FIRST)")
    for table in backup_tables:
        cleanup_sql.append(f"-- DROP TABLE IF EXISTS {table['name']} CASCADE;  -- {table['row_count']:,} rows")
    
    # Save to file
    with open('database_cleanup.sql', 'w') as f:
        f.write('\n'.join(cleanup_sql))
    
    print("\n[OK] Cleanup script saved to: database_cleanup.sql")
    
    # Statistics
    print("\n" + "=" * 80)
    print("STATISTICS")
    print("=" * 80)
    
    total_empty = len(empty_tables)
    total_temp = len(temp_tables)
    total_test = len(test_tables)
    total_backup = len(backup_tables)
    total_droppable = total_empty + total_temp + total_test
    
    droppable_size = sum(t['size_bytes'] for t in empty_tables + temp_tables + test_tables)
    
    print(f"\nTables recommended for immediate drop: {total_droppable}")
    print(f"Space to be reclaimed: {droppable_size / 1024 / 1024:.2f} MB")
    print(f"Tables requiring review: {total_backup + len(legacy_tables)}")
    print(f"Staging tables preserved: {len(staging_tables)}")
    print(f"Core tables: {len(categories['core'])}")

if __name__ == '__main__':
    print("Analyzing database tables...")
    tables = get_all_tables()
    generate_report(tables)
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
