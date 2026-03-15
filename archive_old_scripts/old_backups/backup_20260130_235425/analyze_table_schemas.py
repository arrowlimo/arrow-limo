#!/usr/bin/env python3
"""
Analyze existing almsdata table schemas to determine QB compatibility.
Compare with QB report requirements to assess: extend vs rebuild.
"""
import psycopg2
import json

def connect_db():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REDACTED***'
    )

def get_table_schema(cur, table_name):
    """Get detailed schema for a table."""
    cur.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' 
        AND table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    return cur.fetchall()

def get_table_indexes(cur, table_name):
    """Get indexes for a table."""
    cur.execute("""
        SELECT
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        AND tablename = %s
    """, (table_name,))
    return cur.fetchall()

def analyze_key_tables(cur):
    """Analyze tables most relevant to QB alignment."""
    key_tables = [
        'chart_of_accounts',
        'journal',
        'journal_lines',
        'general_ledger',
        'general_ledger_lines',
        'general_ledger_headers',
        'accounts_receivable',
        'invoices',
        'payables',
        'payments',
        'bank_accounts',
        'banking_transactions',
        'vendors',
        'clients',
        'qb_transactions_staging'
    ]
    
    results = {}
    for table in key_tables:
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema='public' AND table_name=%s
            )
        """, (table,))
        exists = cur.fetchone()[0]
        
        if exists:
            schema = get_table_schema(cur, table)
            indexes = get_table_indexes(cur, table)
            
            # Get row count
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            row_count = cur.fetchone()[0]
            
            results[table] = {
                'exists': True,
                'columns': [(col[0], col[1], col[3]) for col in schema],  # name, type, nullable
                'indexes': [idx[0] for idx in indexes],
                'row_count': row_count
            }
        else:
            results[table] = {'exists': False}
    
    return results

def main():
    conn = connect_db()
    cur = conn.cursor()
    
    print("=" * 80)
    print("ALMSDATA TABLE COMPATIBILITY ASSESSMENT")
    print("=" * 80)
    
    results = analyze_key_tables(cur)
    
    for table, info in results.items():
        print(f"\n{'='*80}")
        print(f"TABLE: {table}")
        print('='*80)
        
        if not info['exists']:
            print("[FAIL] DOES NOT EXIST")
            continue
        
        print(f"✓ EXISTS - {info['row_count']:,} rows")
        print(f"\nColumns ({len(info['columns'])}):")
        for col_name, col_type, nullable in info['columns']:
            null_str = "NULL" if nullable == 'YES' else "NOT NULL"
            print(f"  - {col_name:30} {col_type:20} {null_str}")
        
        print(f"\nIndexes ({len(info['indexes'])}):")
        for idx in info['indexes']:
            print(f"  - {idx}")
    
    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print('='*80)
    existing = [t for t, i in results.items() if i['exists']]
    missing = [t for t, i in results.items() if not i['exists']]
    
    print(f"\n✓ Existing tables ({len(existing)}):")
    for t in existing:
        print(f"  - {t} ({results[t]['row_count']:,} rows)")
    
    if missing:
        print(f"\n[FAIL] Missing tables ({len(missing)}):")
        for t in missing:
            print(f"  - {t}")
    
    # Save detailed results
    output_file = 'L:/limo/table_schema_analysis.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📄 Detailed results saved to: {output_file}")
    
    conn.close()

if __name__ == '__main__':
    main()
