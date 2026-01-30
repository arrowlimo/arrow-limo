#!/usr/bin/env python3
"""
Desktop App Column Validator - Focuses on actual referenced columns
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
        password=os.environ.get('DB_PASSWORD', '***REDACTED***')
    )

def get_table_columns():
    """Get all tables and their actual columns"""
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

def extract_column_references(py_file):
    """Extract column references like table.column from a Python file"""
    try:
        with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except:
        return []
    
    # Find patterns like "e.full_name", "c.charter_id", etc
    pattern = r'\b([a-z_]\w*(?:\d)?)\s*\.\s*([a-z_]\w*)\b'
    matches = re.findall(pattern, content)
    
    return matches

def main():
    schema = get_table_columns()
    
    print("Scanning desktop_app files...")
    desktop_app = Path("l:\\limo\\desktop_app")
    py_files = list(desktop_app.glob("*.py"))
    
    issues = defaultdict(list)
    
    for py_file in sorted(py_files):
        matches = extract_column_references(py_file)
        
        for table_alias, column_name in matches:
            # Skip common non-table aliases
            if table_alias in ['self', 'str', 'int', 'f', 'r', 'QT', 'Qt', 'e', 'os']:
                continue
            
            # Check if column_name looks like a column (not a method)
            if column_name in ['append', 'setText', 'setItem', 'setRowCount', 'addWidget', 
                               'setPlaceholderText', 'setCurrentIndex', 'findText', 'close',
                               'execute', 'fetchone', 'fetchall', 'commit', 'rollback',
                               'get_cursor', 'connect', 'items', 'text', 'currentText', 
                               'value', 'date', 'count', 'row', 'item', 'connect', 'clicked',
                               'textChanged', 'doubleClicked', 'keys', 'values', 'copy', 'get']:
                continue
            
            # Try to match table alias to actual table
            # This is heuristic: e -> employees, c -> charters, etc
            alias_map = {
                'e': ['employees'],
                'c': ['charters'],
                'p': ['payments'],
                'r': ['receipts'],
                'v': ['vehicles'],
                'cl': ['clients'],
                'dp': ['driver_payroll'],
                'f': ['floats'],
                'b': ['banking_transactions'],
                'vt': ['vehicle_types'],
            }
            
            possible_tables = alias_map.get(table_alias, [])
            
            for table in possible_tables:
                if table in schema:
                    if column_name not in schema[table]:
                        issues[(py_file.name, table, column_name)].append((table_alias, column_name))
    
    # Output report
    output_file = "l:\\limo\\reports\\desktop_app_column_audit.txt"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        f.write("="*100 + "\n")
        f.write("DESKTOP APP COLUMN AUDIT - SCHEMA MISMATCH REPORT\n")
        f.write("="*100 + "\n\n")
        
        if not issues:
            f.write("✅ NO ISSUES FOUND - All column references match database schema\n")
        else:
            f.write(f"❌ FOUND {len(issues)} COLUMN MISMATCHES\n\n")
            
            for (filename, table, column), refs in sorted(issues.items()):
                f.write(f"\n{filename} -> {table}.{column}\n")
                f.write(f"  Column '{column}' does not exist in table '{table}'\n")
                f.write(f"  Actual columns in {table}:\n")
                for col in sorted(schema.get(table, [])):
                    f.write(f"    - {col}\n")
        
        # Summary section - show all tables and their columns
        f.write("\n" + "="*100 + "\n")
        f.write("COMPLETE DATABASE SCHEMA REFERENCE\n")
        f.write("="*100 + "\n\n")
        
        for table in sorted(schema.keys()):
            cols = sorted(schema[table])
            f.write(f"\n{table} ({len(cols)} columns)\n")
            f.write(f"  {', '.join(cols)}\n")
    
    print(f"✅ Report saved to: {output_file}")
    
    # Print summary
    print(f"\nTotal tables: {len(schema)}")
    print(f"Total mismatches found: {len(issues)}")
    
    if issues:
        print("\nMismatches:")
        for (filename, table, column), refs in sorted(issues.items())[:10]:
            print(f"  {filename}: {table}.{column}")

if __name__ == '__main__':
    main()
