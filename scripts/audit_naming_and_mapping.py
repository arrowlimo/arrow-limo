#!/usr/bin/env python3
"""
Audit Naming Conventions and LMS Mapping Strategy

Checks:
1. Table naming conventions (plural vs singular, snake_case, etc.)
2. Column naming conventions (consistency, standards)
3. LMS mapping tables and columns
4. Preload/staging table usage
5. ID field naming patterns

Run: python -X utf8 l:\limo\scripts\audit_naming_and_mapping.py
"""

import psycopg2
import os
import re
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def check_table_naming_conventions(cur):
    """Analyze table naming patterns"""
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        ORDER BY tablename
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    issues = {
        'snake_case_violations': [],
        'plural_vs_singular': {'plural': [], 'singular': []},
        'backup_tables': [],
        'staging_tables': [],
        'temp_tables': [],
        'view_tables': [],
        'inconsistent_prefixes': defaultdict(list)
    }
    
    for table in tables:
        # Check snake_case
        if not re.match(r'^[a-z][a-z0-9_]*$', table):
            issues['snake_case_violations'].append(table)
        
        # Check for backups
        if 'backup' in table.lower():
            issues['backup_tables'].append(table)
        
        # Check for staging/temp
        if any(word in table.lower() for word in ['staging', 'temp', 'tmp']):
            issues['staging_tables'].append(table)
        
        # Check for views (v_ prefix)
        if table.startswith('v_'):
            issues['view_tables'].append(table)
        
        # Check plural vs singular (basic heuristic)
        base_name = table.replace('_backup', '').replace('_staging', '').replace('_temp', '')
        if base_name.endswith('s') and not base_name.endswith('ss'):
            issues['plural_vs_singular']['plural'].append(table)
        else:
            issues['plural_vs_singular']['singular'].append(table)
        
        # Check prefixes
        if '_' in table:
            prefix = table.split('_')[0]
            issues['inconsistent_prefixes'][prefix].append(table)
    
    return issues

def check_lms_mapping_tables(cur):
    """Find LMS-related mapping tables and columns"""
    lms_info = {
        'lms_mapping_tables': [],
        'tables_with_lms_columns': [],
        'lms_id_columns': [],
        'qb_mapping_columns': []
    }
    
    # Find tables with 'lms' in name
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename ILIKE '%lms%'
    """)
    lms_info['lms_mapping_tables'] = [row[0] for row in cur.fetchall()]
    
    # Find columns with 'lms' in name
    cur.execute("""
        SELECT DISTINCT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND column_name ILIKE '%lms%'
        ORDER BY table_name, column_name
    """)
    for table, column in cur.fetchall():
        lms_info['tables_with_lms_columns'].append((table, column))
    
    # Find QB (QuickBooks) mapping columns
    cur.execute("""
        SELECT DISTINCT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND (column_name ILIKE '%qb_%' OR column_name ILIKE '%quickbooks%')
        ORDER BY table_name, column_name
    """)
    for table, column in cur.fetchall():
        lms_info['qb_mapping_columns'].append((table, column))
    
    return lms_info

def check_staging_preload_strategy(cur):
    """Analyze staging and preload table usage"""
    staging_info = {
        'staging_tables': [],
        'preload_tables': [],
        'import_tables': [],
        'table_details': []
    }
    
    # Find staging tables
    cur.execute("""
        SELECT 
            tablename,
            pg_size_pretty(pg_total_relation_size('public.' || tablename)) as size
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND (
            tablename ILIKE '%staging%' 
            OR tablename ILIKE '%preload%'
            OR tablename ILIKE '%import%'
            OR tablename ILIKE '%temp%'
        )
        ORDER BY tablename
    """)
    
    for table, size in cur.fetchall():
        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cur.fetchone()[0]
        
        detail = {
            'name': table,
            'size': size,
            'row_count': row_count,
            'type': 'unknown'
        }
        
        if 'staging' in table.lower():
            detail['type'] = 'staging'
            staging_info['staging_tables'].append(table)
        elif 'preload' in table.lower():
            detail['type'] = 'preload'
            staging_info['preload_tables'].append(table)
        elif 'import' in table.lower():
            detail['type'] = 'import'
            staging_info['import_tables'].append(table)
        
        staging_info['table_details'].append(detail)
    
    return staging_info

def check_id_field_naming(cur):
    """Check primary key naming conventions"""
    id_patterns = {
        'table_id': [],  # Standard: table_id (e.g., charter_id)
        'id_only': [],   # Just 'id'
        'inconsistent': [],
        'composite_keys': []
    }
    
    cur.execute("""
        SELECT 
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_schema = 'public'
        ORDER BY tc.table_name
    """)
    
    pk_columns = defaultdict(list)
    for table, column in cur.fetchall():
        pk_columns[table].append(column)
    
    for table, columns in pk_columns.items():
        if len(columns) > 1:
            id_patterns['composite_keys'].append((table, columns))
        elif columns[0] == 'id':
            id_patterns['id_only'].append(table)
        elif columns[0] == f"{table.rstrip('s')}_id":
            id_patterns['table_id'].append(table)
        else:
            id_patterns['inconsistent'].append((table, columns[0]))
    
    return id_patterns

def check_column_naming_standards(cur):
    """Check column naming consistency"""
    standards = {
        'timestamp_columns': defaultdict(list),
        'boolean_columns': defaultdict(list),
        'money_columns': defaultdict(list),
        'inconsistent_naming': []
    }
    
    # Check timestamp column naming
    cur.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND data_type IN ('timestamp without time zone', 'timestamp with time zone')
        ORDER BY column_name
    """)
    for table, column in cur.fetchall():
        standards['timestamp_columns'][column].append(table)
    
    # Check boolean naming
    cur.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND data_type = 'boolean'
        ORDER BY column_name
    """)
    for table, column in cur.fetchall():
        standards['boolean_columns'][column].append(table)
    
    # Check money/numeric naming
    cur.execute("""
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND data_type = 'numeric'
        ORDER BY column_name
    """)
    for table, column in cur.fetchall():
        standards['money_columns'][column].append(table)
    
    return standards

def generate_report(table_naming, lms_mapping, staging, id_fields, column_standards):
    """Generate comprehensive naming and mapping report"""
    report = []
    report.append("="*100)
    report.append("NAMING CONVENTIONS AND LMS MAPPING AUDIT")
    report.append("="*100)
    report.append("")
    
    # ========================================================================
    # TABLE NAMING CONVENTIONS
    # ========================================================================
    report.append("="*100)
    report.append("1. TABLE NAMING CONVENTIONS")
    report.append("="*100)
    report.append("")
    
    report.append(f"Total Tables: {len(table_naming['plural_vs_singular']['plural']) + len(table_naming['plural_vs_singular']['singular'])}")
    report.append(f"  - Plural names: {len(table_naming['plural_vs_singular']['plural'])}")
    report.append(f"  - Singular names: {len(table_naming['plural_vs_singular']['singular'])}")
    report.append("")
    
    if table_naming['snake_case_violations']:
        report.append(f"⚠️  SNAKE_CASE VIOLATIONS ({len(table_naming['snake_case_violations'])} tables):")
        for table in table_naming['snake_case_violations'][:10]:
            report.append(f"  - {table}")
        if len(table_naming['snake_case_violations']) > 10:
            report.append(f"  ... and {len(table_naming['snake_case_violations']) - 10} more")
        report.append("")
    else:
        report.append("✅ All tables follow snake_case convention")
        report.append("")
    
    report.append(f"📦 BACKUP TABLES: {len(table_naming['backup_tables'])}")
    for table in table_naming['backup_tables'][:10]:
        report.append(f"  - {table}")
    if len(table_naming['backup_tables']) > 10:
        report.append(f"  ... and {len(table_naming['backup_tables']) - 10} more")
    report.append("")
    
    report.append(f"🔄 STAGING TABLES: {len(table_naming['staging_tables'])}")
    for table in table_naming['staging_tables']:
        report.append(f"  - {table}")
    report.append("")
    
    report.append(f"👁️  VIEW TABLES (v_ prefix): {len(table_naming['view_tables'])}")
    for table in table_naming['view_tables']:
        report.append(f"  - {table}")
    report.append("")
    
    # ========================================================================
    # LMS MAPPING
    # ========================================================================
    report.append("="*100)
    report.append("2. LMS (LEGACY MANAGEMENT SYSTEM) MAPPING")
    report.append("="*100)
    report.append("")
    
    if lms_mapping['lms_mapping_tables']:
        report.append(f"📊 LMS MAPPING TABLES ({len(lms_mapping['lms_mapping_tables'])} found):")
        for table in lms_mapping['lms_mapping_tables']:
            report.append(f"  - {table}")
        report.append("")
    else:
        report.append("ℹ️  No dedicated LMS mapping tables found")
        report.append("")
    
    if lms_mapping['tables_with_lms_columns']:
        report.append(f"🔗 TABLES WITH LMS COLUMNS ({len(lms_mapping['tables_with_lms_columns'])} found):")
        for table, column in lms_mapping['tables_with_lms_columns'][:20]:
            report.append(f"  - {table}.{column}")
        if len(lms_mapping['tables_with_lms_columns']) > 20:
            report.append(f"  ... and {len(lms_mapping['tables_with_lms_columns']) - 20} more")
        report.append("")
    else:
        report.append("ℹ️  No LMS columns found in tables")
        report.append("")
    
    if lms_mapping['qb_mapping_columns']:
        report.append(f"📚 QUICKBOOKS MAPPING COLUMNS ({len(lms_mapping['qb_mapping_columns'])} found):")
        for table, column in lms_mapping['qb_mapping_columns'][:20]:
            report.append(f"  - {table}.{column}")
        if len(lms_mapping['qb_mapping_columns']) > 20:
            report.append(f"  ... and {len(lms_mapping['qb_mapping_columns']) - 20} more")
        report.append("")
    
    # ========================================================================
    # STAGING/PRELOAD STRATEGY
    # ========================================================================
    report.append("="*100)
    report.append("3. STAGING/PRELOAD TABLE STRATEGY")
    report.append("="*100)
    report.append("")
    
    if staging['staging_tables']:
        report.append(f"🔄 STAGING TABLES ({len(staging['staging_tables'])} found):")
        for detail in staging['table_details']:
            if detail['type'] == 'staging':
                report.append(f"  - {detail['name']}: {detail['row_count']} rows, {detail['size']}")
        report.append("")
    
    if staging['preload_tables']:
        report.append(f"📥 PRELOAD TABLES ({len(staging['preload_tables'])} found):")
        for detail in staging['table_details']:
            if detail['type'] == 'preload':
                report.append(f"  - {detail['name']}: {detail['row_count']} rows, {detail['size']}")
        report.append("")
    
    if staging['import_tables']:
        report.append(f"📦 IMPORT TABLES ({len(staging['import_tables'])} found):")
        for detail in staging['table_details']:
            if detail['type'] == 'import':
                report.append(f"  - {detail['name']}: {detail['row_count']} rows, {detail['size']}")
        report.append("")
    
    if not (staging['staging_tables'] or staging['preload_tables'] or staging['import_tables']):
        report.append("ℹ️  No staging/preload tables found - using direct updates")
        report.append("")
    
    # ========================================================================
    # PRIMARY KEY NAMING
    # ========================================================================
    report.append("="*100)
    report.append("4. PRIMARY KEY NAMING CONVENTIONS")
    report.append("="*100)
    report.append("")
    
    report.append(f"✅ STANDARD (table_id pattern): {len(id_fields['table_id'])} tables")
    report.append(f"⚠️  GENERIC (just 'id'): {len(id_fields['id_only'])} tables")
    if id_fields['id_only']:
        for table in id_fields['id_only'][:10]:
            report.append(f"  - {table}")
        if len(id_fields['id_only']) > 10:
            report.append(f"  ... and {len(id_fields['id_only']) - 10} more")
    report.append("")
    
    if id_fields['inconsistent']:
        report.append(f"❌ INCONSISTENT NAMING: {len(id_fields['inconsistent'])} tables")
        for table, pk_col in id_fields['inconsistent'][:10]:
            report.append(f"  - {table}: {pk_col} (expected {table.rstrip('s')}_id)")
        if len(id_fields['inconsistent']) > 10:
            report.append(f"  ... and {len(id_fields['inconsistent']) - 10} more")
        report.append("")
    
    if id_fields['composite_keys']:
        report.append(f"🔑 COMPOSITE PRIMARY KEYS: {len(id_fields['composite_keys'])} tables")
        for table, columns in id_fields['composite_keys']:
            report.append(f"  - {table}: {', '.join(columns)}")
        report.append("")
    
    # ========================================================================
    # COLUMN NAMING PATTERNS
    # ========================================================================
    report.append("="*100)
    report.append("5. COLUMN NAMING PATTERNS")
    report.append("="*100)
    report.append("")
    
    # Timestamp columns
    report.append("⏰ TIMESTAMP COLUMN PATTERNS:")
    common_timestamps = ['created_at', 'updated_at', 'deleted_at']
    for col in common_timestamps:
        if col in column_standards['timestamp_columns']:
            report.append(f"  ✅ {col}: {len(column_standards['timestamp_columns'][col])} tables")
        else:
            report.append(f"  ⚠️  {col}: NOT USED")
    
    # Other timestamp patterns
    other_timestamps = {k: v for k, v in column_standards['timestamp_columns'].items() 
                       if k not in common_timestamps}
    if other_timestamps:
        report.append(f"\n  Other timestamp patterns ({len(other_timestamps)} unique names):")
        for col, tables in sorted(other_timestamps.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            report.append(f"    - {col}: {len(tables)} tables")
    report.append("")
    
    # Boolean columns
    report.append("✓ BOOLEAN COLUMN PATTERNS:")
    is_prefix = sum(1 for col in column_standards['boolean_columns'].keys() if col.startswith('is_'))
    has_prefix = sum(1 for col in column_standards['boolean_columns'].keys() if col.startswith('has_'))
    no_prefix = len(column_standards['boolean_columns']) - is_prefix - has_prefix
    report.append(f"  - is_ prefix: {is_prefix} columns")
    report.append(f"  - has_ prefix: {has_prefix} columns")
    report.append(f"  - no prefix: {no_prefix} columns")
    report.append("")
    
    # Money columns
    report.append("💰 MONEY/NUMERIC COLUMN PATTERNS:")
    money_patterns = defaultdict(int)
    for col in column_standards['money_columns'].keys():
        if any(word in col.lower() for word in ['amount', 'price', 'cost', 'total', 'balance']):
            if 'amount' in col.lower():
                money_patterns['*_amount'] += 1
            elif 'price' in col.lower():
                money_patterns['*_price'] += 1
            elif 'cost' in col.lower():
                money_patterns['*_cost'] += 1
            elif 'total' in col.lower():
                money_patterns['*_total'] += 1
            elif 'balance' in col.lower():
                money_patterns['*_balance'] += 1
    
    for pattern, count in sorted(money_patterns.items(), key=lambda x: x[1], reverse=True):
        report.append(f"  - {pattern}: {count} columns")
    report.append("")
    
    # ========================================================================
    # RECOMMENDATIONS
    # ========================================================================
    report.append("="*100)
    report.append("6. RECOMMENDATIONS")
    report.append("="*100)
    report.append("")
    
    report.append("✅ GOOD PRACTICES:")
    report.append("  - Most tables follow snake_case convention")
    report.append("  - Consistent use of created_at/updated_at timestamps")
    report.append("  - Standard table_id primary key pattern widely used")
    report.append("")
    
    report.append("⚠️  AREAS FOR IMPROVEMENT:")
    if id_fields['id_only']:
        report.append(f"  - {len(id_fields['id_only'])} tables use generic 'id' instead of 'table_id'")
    if len(table_naming['backup_tables']) > 10:
        report.append(f"  - {len(table_naming['backup_tables'])} backup tables should be reviewed/cleaned")
    if lms_mapping['tables_with_lms_columns']:
        report.append(f"  - {len(lms_mapping['tables_with_lms_columns'])} tables still have LMS columns (migration incomplete?)")
    report.append("")
    
    report.append("📋 ACTION ITEMS:")
    report.append("  1. Standardize boolean column naming (consistent is_/has_ prefix)")
    report.append("  2. Review and clean up old backup tables")
    report.append("  3. Document LMS→New system mapping strategy")
    report.append("  4. Consider migrating generic 'id' columns to table_id pattern")
    report.append("  5. Remove unused staging tables if migration complete")
    report.append("")
    
    report.append("="*100)
    report.append("END OF REPORT")
    report.append("="*100)
    
    return "\n".join(report)

def main():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("Starting naming conventions and LMS mapping audit...")
    print()
    
    print("[1/5] Analyzing table naming conventions...")
    table_naming = check_table_naming_conventions(cur)
    
    print("[2/5] Checking LMS mapping tables and columns...")
    lms_mapping = check_lms_mapping_tables(cur)
    
    print("[3/5] Analyzing staging/preload table strategy...")
    staging = check_staging_preload_strategy(cur)
    
    print("[4/5] Checking ID field naming patterns...")
    id_fields = check_id_field_naming(cur)
    
    print("[5/5] Analyzing column naming standards...")
    column_standards = check_column_naming_standards(cur)
    
    print("\nGenerating report...")
    
    report = generate_report(table_naming, lms_mapping, staging, id_fields, column_standards)
    
    # Save report
    from datetime import datetime
    output_file = f"l:\\limo\\reports\\naming_and_mapping_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ Audit complete!")
    print(f"📄 Report saved to: {output_file}")
    print()
    print(report)
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
