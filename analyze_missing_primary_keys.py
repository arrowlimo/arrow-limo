"""
Analyze Tables Without Primary Keys
====================================
Find tables missing primary keys and categorize by usage/importance.

After deleting 17 duplicate tables, ~140 tables remain without PKs.
This script identifies which ones:
1. Are actively used in code
2. Have data (row count > 0)
3. Are part of core business logic
4. Can be safely deleted
"""

import psycopg2
import json
from datetime import datetime
from pathlib import Path

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

def get_tables_without_pks(cur):
    """Get all tables that don't have a primary key."""
    cur.execute("""
        SELECT t.table_name
        FROM information_schema.tables t
        LEFT JOIN information_schema.table_constraints tc 
            ON t.table_name = tc.table_name 
            AND tc.constraint_type = 'PRIMARY KEY'
        WHERE t.table_schema = 'public' 
            AND t.table_type = 'BASE TABLE'
            AND tc.constraint_name IS NULL
        ORDER BY t.table_name
    """)
    return [row[0] for row in cur.fetchall()]

def get_table_info(cur, table_name):
    """Get detailed info about a table."""
    # Get row count
    try:
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]
    except:
        row_count = None
    
    # Get size
    try:
        cur.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))")
        size = cur.fetchone()[0]
    except:
        size = None
    
    # Get columns
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    columns = cur.fetchall()
    
    # Check for likely PK candidates (id columns)
    pk_candidates = [
        col[0] for col in columns 
        if col[0].endswith('_id') or col[0] == 'id' or col[0].endswith('_number')
    ]
    
    # Check for foreign keys
    cur.execute("""
        SELECT 
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' 
            AND tc.table_name = %s
    """, (table_name,))
    foreign_keys = cur.fetchall()
    
    return {
        'row_count': row_count,
        'size': size,
        'column_count': len(columns),
        'columns': [col[0] for col in columns],
        'pk_candidates': pk_candidates,
        'foreign_keys': len(foreign_keys),
        'nullable_columns': sum(1 for col in columns if col[2] == 'YES')
    }

def categorize_table(table_name, info):
    """Categorize table based on naming patterns and usage."""
    name_lower = table_name.lower()
    
    # Core business tables
    if any(x in name_lower for x in ['charter', 'client', 'payment', 'receipt', 'vehicle', 'driver', 'employee']):
        return 'CORE_BUSINESS'
    
    # Accounting/financial
    if any(x in name_lower for x in ['ledger', 'account', 'transaction', 'invoice', 'journal']):
        return 'ACCOUNTING'
    
    # Staging/temporary
    if any(x in name_lower for x in ['staging', 'temp', 'tmp', 'backup', 'archive', 'old']):
        return 'STAGING_TEMP'
    
    # Reference/lookup
    if any(x in name_lower for x in ['lookup', 'reference', 'type', 'status', 'category']):
        return 'REFERENCE'
    
    # Audit/logging
    if any(x in name_lower for x in ['log', 'audit', 'history', 'change']):
        return 'AUDIT_LOG'
    
    # Migration/legacy
    if any(x in name_lower for x in ['migration', 'legacy', 'import', 'export']):
        return 'MIGRATION'
    
    return 'OTHER'

def main():
    print("=" * 80)
    print("ANALYZING TABLES WITHOUT PRIMARY KEYS")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print()
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Get all tables without PKs
        tables_no_pk = get_tables_without_pks(cur)
        print(f"Found {len(tables_no_pk)} tables without primary keys")
        print()
        
        # Analyze each table
        print("Analyzing table details...")
        print("-" * 80)
        
        results = {}
        categories = {}
        
        for table in tables_no_pk:
            info = get_table_info(cur, table)
            category = categorize_table(table, info)
            
            results[table] = {
                **info,
                'category': category
            }
            
            if category not in categories:
                categories[category] = []
            categories[category].append(table)
            
            # Print progress
            status = "✅ EMPTY" if info['row_count'] == 0 else f"📊 {info['row_count']:,} rows"
            pk_info = f"PK candidates: {', '.join(info['pk_candidates'][:3])}" if info['pk_candidates'] else "No PK candidates"
            print(f"  {table:<50} {status:<20} {pk_info}")
        
        print()
        print("=" * 80)
        print("SUMMARY BY CATEGORY")
        print("=" * 80)
        
        priority_order = [
            'CORE_BUSINESS',
            'ACCOUNTING',
            'REFERENCE',
            'AUDIT_LOG',
            'MIGRATION',
            'STAGING_TEMP',
            'OTHER'
        ]
        
        for category in priority_order:
            if category not in categories:
                continue
            
            tables = categories[category]
            total_rows = sum(results[t]['row_count'] or 0 for t in tables)
            with_data = sum(1 for t in tables if (results[t]['row_count'] or 0) > 0)
            
            print()
            print(f"📂 {category}")
            print(f"   Tables: {len(tables)} | With data: {with_data} | Total rows: {total_rows:,}")
            print()
            
            for table in sorted(tables):
                info = results[table]
                row_info = f"{info['row_count']:,}" if info['row_count'] else "0"
                pk_cand = info['pk_candidates'][0] if info['pk_candidates'] else "NONE"
                print(f"      {table:<45} {row_info:>12} rows | PK: {pk_cand}")
        
        # Generate recommendations
        print()
        print("=" * 80)
        print("RECOMMENDATIONS")
        print("=" * 80)
        print()
        
        # High priority - core business tables
        core_with_data = [
            t for t in categories.get('CORE_BUSINESS', [])
            if (results[t]['row_count'] or 0) > 0
        ]
        if core_with_data:
            print("🔴 HIGH PRIORITY - Add PKs to core business tables:")
            for table in core_with_data:
                pk_cand = results[table]['pk_candidates'][0] if results[table]['pk_candidates'] else "CREATE SERIAL"
                print(f"   ALTER TABLE {table} ADD PRIMARY KEY ({pk_cand});")
            print()
        
        # Medium priority - accounting/reference
        accounting_with_data = [
            t for t in categories.get('ACCOUNTING', []) + categories.get('REFERENCE', [])
            if (results[t]['row_count'] or 0) > 0
        ]
        if accounting_with_data:
            print("🟡 MEDIUM PRIORITY - Add PKs to accounting/reference tables:")
            print(f"   {len(accounting_with_data)} tables")
            print()
        
        # Safe to delete - empty staging/temp
        empty_staging = [
            t for t in categories.get('STAGING_TEMP', [])
            if (results[t]['row_count'] or 0) == 0
        ]
        if empty_staging:
            print("🟢 SAFE TO DELETE - Empty staging/temp tables:")
            for table in empty_staging:
                print(f"   DROP TABLE IF EXISTS {table};")
            print()
        
        # Save results
        output_dir = Path('L:/limo/reports')
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = output_dir / f'missing_pk_analysis_{timestamp}.json'
        
        with open(json_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'total_tables': len(tables_no_pk),
                'categories': {k: len(v) for k, v in categories.items()},
                'tables': results
            }, f, indent=2, default=str)
        
        print(f"📄 Full results saved to: {json_file}")
        print()
        print("=" * 80)
        print(f"Completed: {datetime.now()}")
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
