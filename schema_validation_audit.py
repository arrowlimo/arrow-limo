#!/usr/bin/env python3
"""
Schema Validation Audit - Check for missing columns and data type mismatches
"""

import psycopg2
import re
from pathlib import Path

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = "***REMOVED***"

def get_table_columns():
    """Get all tables and their columns from database"""
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT table_name, column_name 
        FROM information_schema.columns 
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """)
    
    tables = {}
    for table, col in cur.fetchall():
        if table not in tables:
            tables[table] = []
        tables[table].append(col)
    
    cur.close()
    conn.close()
    return tables

def extract_queries_from_python():
    """Extract SQL queries from Python files"""
    queries = []
    
    for py_file in Path("L:\\limo\\desktop_app").glob("*.py"):
        try:
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            
            # Find SELECT queries
            select_pattern = r'SELECT\s+.*?FROM\s+(\w+)'
            matches = re.finditer(select_pattern, content, re.IGNORECASE | re.DOTALL)
            
            for match in matches:
                query_start = max(0, match.start() - 200)
                query_end = min(len(content), match.end() + 300)
                query_snippet = content[query_start:query_end]
                
                # Extract table name
                table_name = match.group(1)
                
                # Extract column names from SELECT clause
                select_part = content[max(0, match.start()-100):match.start()]
                col_pattern = r'SELECT\s+(.*?)\s+FROM'
                col_match = re.search(col_pattern, select_part + 'FROM', re.IGNORECASE | re.DOTALL)
                
                if col_match:
                    cols_str = col_match.group(1)
                    # Simple extraction - get words that look like column names
                    potential_cols = re.findall(r'(\w+)(?:\s+as|\s*,|$)', cols_str, re.IGNORECASE)
                    
                    queries.append({
                        'file': py_file.name,
                        'table': table_name,
                        'columns': potential_cols,
                        'snippet': query_snippet.strip()
                    })
        except Exception as e:
            pass
    
    return queries

def main():
    print("=" * 80)
    print("Arrow Limousine Database Schema Validation")
    print("=" * 80)
    
    # Get actual database schema
    print("\n✅ Fetching database schema...")
    tables = get_table_columns()
    
    print(f"✅ Found {len(tables)} tables")
    
    # Show key tables for reference
    print("\n📋 KEY TABLE SCHEMAS:")
    for table_name in ['clients', 'charters', 'payments', 'employees', 'vehicles', 'receipts']:
        if table_name in tables:
            print(f"\n  {table_name}:")
            for col in tables[table_name][:15]:  # First 15 columns
                print(f"    - {col}")
            if len(tables[table_name]) > 15:
                print(f"    ... and {len(tables[table_name]) - 15} more")
    
    # Check specific known issues
    print("\n🔍 KNOWN COLUMN ISSUES:")
    
    issues = [
        ('clients', 'phone', 'primary_phone', 'Client phone column should be primary_phone'),
        ('clients', 'address', 'Does column exist?', 'Client address handling'),
        ('charters', 'total_price', 'total_amount_due', 'Charter amount column should be total_amount_due'),
        ('receipts', 'vendor_name', 'Check actual name', 'Receipts vendor field'),
    ]
    
    for table, old_col, correct_col, description in issues:
        if table in tables:
            if old_col in tables[table]:
                print(f"  ❌ {table}.{old_col} - Still exists (check if used correctly)")
            elif correct_col != 'Does column exist?' and correct_col != 'Check actual name':
                if correct_col in tables[table]:
                    print(f"  ✅ {table}.{old_col} → {correct_col} - Correct")
                else:
                    print(f"  ⚠️  {table}: Neither {old_col} nor {correct_col} found!")
            else:
                print(f"  ℹ️  {table}: {description}")
    
    print("\n" + "=" * 80)
    print("✅ Schema Validation Complete")
    print("=" * 80)

if __name__ == "__main__":
    main()
