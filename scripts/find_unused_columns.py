#!/usr/bin/env python3
"""
Find all database columns NOT referenced in desktop_app code
Identifies unused/underutilized columns in the schema
"""

import psycopg2
import os
import re
from pathlib import Path
from collections import defaultdict

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        database=os.environ.get('DB_NAME', 'almsdata'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', '***REMOVED***')
    )

def get_all_columns():
    """Get all columns from all tables"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    schema = {}
    for table in tables:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
        """, (table,))
        schema[table] = set(row[0] for row in cur.fetchall())
    
    cur.close()
    conn.close()
    return schema

def extract_referenced_columns(py_file):
    """Extract all column references from a Python file"""
    try:
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return set()
    
    referenced = set()
    
    # Pattern: table_alias.column_name
    pattern = r'\b([a-z_]\w*)\s*\.\s*([a-z_]\w*)\b'
    matches = re.findall(pattern, content)
    
    for alias, column in matches:
        # Skip common non-column references
        if not any(x in column for x in ['append', 'setText', 'setItem', 'text', 
                                          'value', 'count', 'execute', 'fetchone', 
                                          'fetchall', 'commit', 'rollback', 'close',
                                          'get_cursor', 'connect', 'items', 'keys',
                                          'values', 'row', 'item', 'clicked', 'textChanged',
                                          'doubleClicked', 'copy', 'get', 'setCurrentIndex',
                                          'findText', 'setPlaceholderText', 'addWidget']):
            referenced.add(column)
    
    return referenced

def main():
    print("Analyzing database schema usage...")
    
    schema = get_all_columns()
    desktop_app = Path("l:\\limo\\desktop_app")
    py_files = list(desktop_app.glob("*.py"))
    
    # Collect all referenced columns across all files
    all_referenced = set()
    for py_file in py_files:
        refs = extract_referenced_columns(py_file)
        all_referenced.update(refs)
    
    # Find unused columns per table
    unused_by_table = {}
    used_by_table = {}
    
    for table in sorted(schema.keys()):
        columns = schema[table]
        unused = columns - all_referenced
        used = columns & all_referenced
        
        if unused:
            unused_by_table[table] = sorted(unused)
        if used:
            used_by_table[table] = sorted(used)
    
    # Generate report
    output_file = "l:\\limo\\reports\\unused_database_columns.txt"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("="*100 + "\n")
        f.write("UNUSED DATABASE COLUMNS - COLUMNS NOT REFERENCED IN DESKTOP APP\n")
        f.write("="*100 + "\n\n")
        
        total_columns = sum(len(cols) for cols in schema.values())
        total_used = len(all_referenced)
        total_unused = total_columns - total_used
        
        f.write(f"SUMMARY:\n")
        f.write(f"  Total database columns: {total_columns}\n")
        f.write(f"  Referenced in app: {total_used} ({100*total_used//total_columns}%)\n")
        f.write(f"  Not referenced: {total_unused} ({100*total_unused//total_columns}%)\n\n")
        
        # Core tables (most important)
        core_tables = ['charters', 'clients', 'employees', 'vehicles', 'payments', 
                      'receipts', 'driver_payroll', 'banking_transactions']
        
        f.write("\n" + "="*100 + "\n")
        f.write("CORE TABLES - UNUSED COLUMNS\n")
        f.write("="*100 + "\n\n")
        
        for table in core_tables:
            if table in unused_by_table:
                unused = unused_by_table[table]
                used = len(used_by_table.get(table, []))
                total = len(schema[table])
                f.write(f"\n{table} ({used}/{total} columns used)\n")
                f.write("-"*100 + "\n")
                for col in unused:
                    f.write(f"  ❌ {col}\n")
            else:
                used = len(used_by_table.get(table, []))
                total = len(schema[table])
                f.write(f"\n{table} ({used}/{total} columns used) ✅ ALL USED\n")
        
        # Other tables
        f.write("\n\n" + "="*100 + "\n")
        f.write("OTHER TABLES - UNUSED COLUMNS\n")
        f.write("="*100 + "\n\n")
        
        for table in sorted(unused_by_table.keys()):
            if table not in core_tables:
                unused = unused_by_table[table]
                used = len(used_by_table.get(table, []))
                total = len(schema[table])
                f.write(f"\n{table} ({used}/{total} columns used)\n")
                f.write("-"*100 + "\n")
                for col in unused[:10]:  # Show first 10
                    f.write(f"  ❌ {col}\n")
                if len(unused) > 10:
                    f.write(f"  ... and {len(unused)-10} more\n")
        
        # Detailed reference list
        f.write("\n\n" + "="*100 + "\n")
        f.write("ALL REFERENCED COLUMNS\n")
        f.write("="*100 + "\n\n")
        
        for col in sorted(all_referenced)[:50]:
            f.write(f"  ✅ {col}\n")
        
        if len(all_referenced) > 50:
            f.write(f"  ... and {len(all_referenced)-50} more columns\n")
    
    print(f"\n✅ Report saved to: {output_file}")
    
    # Print summary
    print(f"\n" + "="*80)
    print("COLUMN USAGE SUMMARY")
    print("="*80)
    print(f"Total database columns: {total_columns}")
    print(f"Referenced in desktop_app: {total_used} ({100*total_used//total_columns}%)")
    print(f"NOT referenced: {total_unused} ({100*total_unused//total_columns}%)")
    
    # Show core tables
    print(f"\nCORE TABLES:")
    for table in core_tables:
        unused = len(unused_by_table.get(table, []))
        used = len(used_by_table.get(table, []))
        total = len(schema[table])
        status = "✅" if unused == 0 else "⚠️"
        print(f"  {status} {table}: {used}/{total} columns used ({unused} unused)")
        if unused > 0 and unused <= 5:
            for col in unused_by_table[table]:
                print(f"      - {col}")

if __name__ == '__main__':
    main()
