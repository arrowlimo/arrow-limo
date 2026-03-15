#!/usr/bin/env python3
"""
Comprehensive Desktop App Schema Audit
Extracts all actual database tables/columns and compares against desktop_app code
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

def get_all_tables_and_columns():
    """Extract all tables and their columns from database"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
        ORDER BY table_name
    """)
    tables = [row[0] for row in cur.fetchall()]
    
    schema = {}
    for table in tables:
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table,))
        schema[table] = {row[0]: row[1] for row in cur.fetchall()}
    
    cur.close()
    conn.close()
    return schema

def extract_sql_references(py_file):
    """Extract all SQL column/table references from a Python file"""
    with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # Find all SQL queries
    sql_patterns = [
        r'cur\.execute\s*\(\s*["\']([^"\']+)["\']',  # Direct string
        r'cur\.execute\s*\(\s*f["\']([^"\']+)["\']',  # f-string
        r'INSERT INTO\s+(\w+)',
        r'SELECT\s+(.+?)\s+FROM',
        r'UPDATE\s+(\w+)',
        r'DELETE FROM\s+(\w+)',
        r'LEFT JOIN\s+(\w+)',
        r'INNER JOIN\s+(\w+)',
    ]
    
    references = {
        'queries': [],
        'tables': set(),
        'columns': set()
    }
    
    # Extract full queries
    query_match = re.findall(r'"""(.*?)"""', content, re.DOTALL)
    for query in query_match:
        references['queries'].append(query)
    
    # Extract table references
    for pattern in sql_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            if isinstance(match, str) and match.strip():
                # Extract table name
                table_match = re.search(r'FROM\s+(\w+)|INTO\s+(\w+)|UPDATE\s+(\w+)', match, re.IGNORECASE)
                if table_match:
                    table = next(g for g in table_match.groups() if g)
                    references['tables'].add(table)
    
    # Extract column references with table alias
    col_pattern = r'([a-z_]\w*)\.\w+'
    matches = re.findall(col_pattern, content)
    references['columns'].update(matches)
    
    return references

def main():
    print("\n" + "="*100)
    print("DESKTOP APP SCHEMA AUDIT - COMPREHENSIVE COLUMN/TABLE VALIDATION")
    print("="*100)
    
    # Get actual database schema
    print("\n[1/3] Extracting database schema...")
    schema = get_all_tables_and_columns()
    print(f"  ✓ Found {len(schema)} tables")
    
    print("\n" + "="*100)
    print("DATABASE SCHEMA")
    print("="*100)
    for table in sorted(schema.keys()):
        cols = schema[table]
        print(f"\n📋 {table} ({len(cols)} columns)")
        for col, dtype in sorted(cols.items()):
            print(f"   - {col:<40} {dtype}")
    
    # Scan desktop_app files
    print("\n" + "="*100)
    print("[2/3] Scanning desktop_app Python files...")
    print("="*100)
    
    desktop_app = Path("l:\\limo\\desktop_app")
    py_files = list(desktop_app.glob("*.py"))
    print(f"  ✓ Found {len(py_files)} Python files")
    
    all_issues = defaultdict(list)
    file_analysis = {}
    
    for py_file in sorted(py_files):
        refs = extract_sql_references(py_file)
        file_analysis[py_file.name] = refs
        
        # Check table references
        for table in refs['tables']:
            if table not in schema:
                all_issues['missing_table'].append((py_file.name, table))
    
    # Report missing tables
    print("\n" + "="*100)
    print("[3/3] AUDIT RESULTS")
    print("="*100)
    
    if all_issues['missing_table']:
        print("\n❌ MISSING TABLES (referenced in code but not in database):")
        for file, table in all_issues['missing_table']:
            print(f"   {file}: {table}")
    
    # Detailed file analysis
    print("\n" + "="*100)
    print("DETAILED FILE ANALYSIS")
    print("="*100)
    
    for filename in sorted(file_analysis.keys()):
        refs = file_analysis[filename]
        if refs['tables'] or refs['columns']:
            print(f"\n📄 {filename}")
            if refs['tables']:
                print(f"   Tables referenced: {', '.join(sorted(refs['tables']))}")
            if refs['columns']:
                print(f"   Table aliases used: {', '.join(sorted(refs['columns']))}")
            
            # Show first 3 queries
            if refs['queries']:
                print(f"   Queries ({len(refs['queries'])} total):")
                for i, query in enumerate(refs['queries'][:3], 1):
                    lines = query.strip().split('\n')[:2]
                    query_preview = ' '.join(lines)[:100]
                    print(f"      {i}. {query_preview}...")
    
    # Summary
    print("\n" + "="*100)
    print("SUMMARY")
    print("="*100)
    print(f"Total tables in database: {len(schema)}")
    print(f"Total Python files scanned: {len(py_files)}")
    print(f"Missing table references: {len(all_issues['missing_table'])}")
    
    if not all_issues['missing_table']:
        print("\n✅ All table references are valid!")
    
    print("\n" + "="*100)

if __name__ == '__main__':
    main()
