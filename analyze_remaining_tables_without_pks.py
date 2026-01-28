"""
Analyze Remaining 9 Tables Without PKs
=======================================
These are mostly reporting/verification tables.
Check if they need:
1. Composite primary keys
2. Serial ID column added
3. Can be converted to views
4. Should remain as-is (reporting snapshots)
"""

import psycopg2
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'database': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***'
}

REMAINING_TABLES = [
    # Accounting verification (1-row snapshots)
    'accounting_books_final_verification',
    'accounting_system_verification',
    'etransfer_accounting_assessment',
    'etransfer_analysis_results',
    'etransfer_fix_final_results',
    
    # Financial reports (aggregated data)
    'balance_sheet',
    'profit_and_loss',
    'trial_balance',
    
    # Suppliers (reference data)
    'suppliers',
]

def analyze_table_structure(cur, table):
    """Determine best PK strategy for a table."""
    # Get all columns
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table}'
        ORDER BY ordinal_position
    """)
    columns = cur.fetchall()
    
    # Get row count
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    row_count = cur.fetchone()[0]
    
    # Get sample data
    cur.execute(f"SELECT * FROM {table} LIMIT 3")
    sample = cur.fetchall()
    
    # Check for potential composite PK
    non_nullable_cols = [c[0] for c in columns if c[2] == 'NO']
    
    # Check if it's a snapshot table (1 row)
    is_snapshot = row_count <= 1
    
    # Check if it looks like a report view (aggregated data)
    is_report = any(word in table for word in ['balance_sheet', 'profit_and_loss', 'trial_balance'])
    
    return {
        'table': table,
        'row_count': row_count,
        'column_count': len(columns),
        'columns': [c[0] for c in columns],
        'non_nullable': non_nullable_cols,
        'is_snapshot': is_snapshot,
        'is_report': is_report,
        'sample_data': sample[:1]  # Just first row
    }

def recommend_solution(analysis):
    """Recommend best solution for adding PK."""
    table = analysis['table']
    row_count = analysis['row_count']
    
    if analysis['is_snapshot']:
        return {
            'recommendation': 'ADD_SERIAL_ID',
            'reason': 'Single-row snapshot table',
            'sql': f"ALTER TABLE {table} ADD COLUMN snapshot_id SERIAL PRIMARY KEY;"
        }
    
    if analysis['is_report']:
        return {
            'recommendation': 'ADD_SERIAL_ID or CONVERT_TO_VIEW',
            'reason': 'Reporting table - probably should be a materialized view',
            'sql': f"ALTER TABLE {table} ADD COLUMN report_row_id SERIAL PRIMARY KEY;"
        }
    
    if table == 'suppliers':
        # Check if has supplier_id or name
        if 'supplier_id' in analysis['columns']:
            return {
                'recommendation': 'USE_EXISTING_COLUMN',
                'reason': 'Has supplier_id column',
                'sql': f"ALTER TABLE {table} ADD PRIMARY KEY (supplier_id);"
            }
        elif 'name' in analysis['columns'] or 'supplier_name' in analysis['columns']:
            return {
                'recommendation': 'ADD_SERIAL_ID',
                'reason': 'Suppliers should have unique ID',
                'sql': f"ALTER TABLE {table} ADD COLUMN supplier_id SERIAL PRIMARY KEY;"
            }
    
    return {
        'recommendation': 'ADD_SERIAL_ID',
        'reason': 'Generic solution',
        'sql': f"ALTER TABLE {table} ADD COLUMN id SERIAL PRIMARY KEY;"
    }

def main():
    print("=" * 80)
    print("ANALYZING REMAINING 9 TABLES WITHOUT PRIMARY KEYS")
    print("=" * 80)
    print(f"Started: {datetime.now()}")
    print()
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        for table in REMAINING_TABLES:
            print(f"\n{'='*60}")
            print(f"TABLE: {table}")
            print(f"{'='*60}")
            
            analysis = analyze_table_structure(cur, table)
            recommendation = recommend_solution(analysis)
            
            print(f"Rows: {analysis['row_count']}")
            print(f"Columns: {analysis['column_count']}")
            print(f"Type: {'SNAPSHOT' if analysis['is_snapshot'] else 'REPORT' if analysis['is_report'] else 'DATA'}")
            print()
            print(f"📋 Recommendation: {recommendation['recommendation']}")
            print(f"   Reason: {recommendation['reason']}")
            print(f"   SQL: {recommendation['sql']}")
        
        print()
        print("=" * 80)
        print("SUMMARY OF RECOMMENDATIONS")
        print("=" * 80)
        print()
        print("Option 1: Add SERIAL PKs to all 9 tables (quick fix)")
        print("Option 2: Convert balance_sheet, profit_and_loss, trial_balance to views")
        print("Option 3: Leave snapshot tables as-is (they're just verification records)")
        print()
        print("RECOMMENDED APPROACH:")
        print("  - Add SERIAL PKs to suppliers (784 rows - actual data)")
        print("  - Leave 8 reporting/verification tables as-is (not critical)")
        print()
        
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    main()
