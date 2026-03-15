#!/usr/bin/env python3
"""
Comprehensive audit for dead code column references.
Compares code SELECT statements with actual database schema.
"""
import os
import re
import psycopg2
from collections import defaultdict

# Database connection for Neon
DB_HOST = "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"
DB_NAME = "neondb"
DB_USER = "neondb_owner"
DB_PASSWORD = "npg_89MbcFmZwUWo"

def get_db_columns():
    """Fetch all columns from critical tables"""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, sslmode="require"
    )
    cur = conn.cursor()
    
    tables = ['charters', 'payments', 'receipts', 'clients', 'employees', 'vehicles']
    schema = {}
    
    for table in tables:
        cur.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (table,))
        schema[table] = [row[0] for row in cur.fetchall()]
    
    cur.close()
    conn.close()
    
    return schema

def scan_python_files():
    """Scan Python files for column references"""
    patterns = {
        'direct_select': r'SELECT\s+([^FROM]+)\s+FROM\s+(\w+)',
        'column_access': r'(\w+)\s*=\s*row\[(\d+)\]',
        'tuple_unpack': r'(\w+(?:\s*,\s*\w+)+)\s*=\s*(?:cur\.fetchone|row)',
    }
    
    code_references = defaultdict(list)
    
    for root, dirs, files in os.walk(r'l:\limo\desktop_app'):
        for file in files:
            if not file.endswith('.py'):
                continue
            
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Find all SELECT statements
                    for match in re.finditer(r'SELECT\s+([^F]+?)\s+FROM\s+(\w+)(?:\s|WHERE|$)', content, re.IGNORECASE):
                        cols_str = match.group(1).strip()
                        table = match.group(2).lower()
                        
                        # Parse column names (simple extraction)
                        cols = [c.strip().split()[-1] for c in cols_str.split(',')]
                        code_references[table].extend([(col, filepath) for col in cols if col and not col.startswith('%')])
            except Exception as e:
                print(f"Error scanning {filepath}: {e}")
    
    return code_references

def audit():
    """Run the audit"""
    print("=" * 80)
    print("DEAD CODE COLUMN AUDIT")
    print("=" * 80)
    
    schema = get_db_columns()
    print("\n✅ DATABASE SCHEMA:")
    for table, cols in schema.items():
        print(f"  {table}: {len(cols)} columns")
    
    code_refs = scan_python_files()
    print("\n📝 CODE REFERENCES FOUND:")
    for table, refs in sorted(code_refs.items()):
        if table in schema:
            unique_cols = set([col.replace('c.', '').replace('p.', '').replace('r.', '').replace('e.', '').replace('v.', '') for col, _ in refs])
            db_cols = set(schema[table])
            
            missing = unique_cols - db_cols
            if missing:
                print(f"\n⚠️  {table.upper()}: {len(missing)} MISSING COLUMNS")
                for col in sorted(missing):
                    print(f"     - {col}")
            else:
                print(f"\n✅ {table.upper()}: All {len(unique_cols)} referenced columns exist")

if __name__ == '__main__':
    audit()
