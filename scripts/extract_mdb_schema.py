#!/usr/bin/env python
"""
Extract schema from MDB backup and compare with current almsdata
"""
import pyodbc
import json
import os
import psycopg2
from datetime import datetime

def extract_mdb_schema():
    """Extract table schema from MDB backup"""
    mdb_path = r"L:\limo\backups\lms.mdb"
    schema = {}
    
    try:
        conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Get all tables
        tables = {}
        for table_info in cursor.tables(tableType='TABLE'):
            table_name = table_info[2]
            tables[table_name] = []
        
        # Get columns for each table
        for table_name in tables.keys():
            columns = []
            try:
                col_cursor = cursor.columns(table=table_name)
                for col_info in col_cursor:
                    columns.append({
                        'name': col_info[3],
                        'type': str(col_info[5]),
                        'nullable': col_info[17] == 'YES' if col_info[17] else True,
                        'size': col_info[6] if col_info[6] else None
                    })
            except Exception as e:
                print(f"Error reading columns for {table_name}: {e}")
            
            schema[table_name] = {
                'columns': columns,
                'column_count': len(columns),
                'source': 'lms.mdb',
                'extracted': datetime.now().isoformat()
            }
        
        conn.close()
        return schema
    except Exception as e:
        print(f"Error connecting to MDB: {e}")
        print("Make sure Microsoft Access Driver is installed")
        return {}

def get_postgres_schema():
    """Get schema from current PostgreSQL almsdata"""
    schema = {}
    
    try:
        # Create a fresh connection with autocommit
        conn = psycopg2.connect(
            host="localhost",
            database="almsdata",
            user="postgres",
            password="***REMOVED***"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Get all tables in public schema
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        for table_name in tables:
            try:
                columns = []
                cursor.execute(f"""
                    SELECT 
                        column_name, 
                        data_type, 
                        is_nullable,
                        column_default
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """)
                
                for col_name, col_type, nullable, default in cursor.fetchall():
                    columns.append({
                        'name': col_name,
                        'type': col_type,
                        'nullable': nullable == 'YES',
                        'default': default
                    })
                
                # Get row count
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
                    row_count = cursor.fetchone()[0]
                except:
                    row_count = None
                
                # Get last modified (from table stats if available)
                last_mod = None
                
                schema[table_name] = {
                    'columns': columns,
                    'column_count': len(columns),
                    'row_count': row_count,
                    'source': 'almsdata',
                    'last_modified': last_mod.isoformat() if last_mod else None,
                    'extracted': datetime.now().isoformat()
                }
            except Exception as e:
                # Skip tables with errors but continue
                print(f"  Skipped {table_name}: {str(e)[:100]}")
                continue
        
        conn.close()
        return schema
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return {}

def compare_schemas(mdb_schema, pg_schema):
    """Compare MDB and PostgreSQL schemas"""
    comparison = {
        'extracted': datetime.now().isoformat(),
        'mdb_tables': len(mdb_schema),
        'pg_tables': len(pg_schema),
        'tables': {}
    }
    
    all_tables = set(list(mdb_schema.keys()) + list(pg_schema.keys()))
    
    for table in sorted(all_tables):
        mdb_cols = {col['name'] for col in mdb_schema.get(table, {}).get('columns', [])}
        pg_cols = {col['name'] for col in pg_schema.get(table, {}).get('columns', [])}
        
        comparison['tables'][table] = {
            'in_mdb': table in mdb_schema,
            'in_pg': table in pg_schema,
            'mdb_columns': len(mdb_cols) if mdb_cols else 0,
            'pg_columns': len(pg_cols) if pg_cols else 0,
            'columns_added': list(pg_cols - mdb_cols) if pg_cols and mdb_cols else [],
            'columns_removed': list(mdb_cols - pg_cols) if mdb_cols and pg_cols else [],
            'pg_row_count': pg_schema.get(table, {}).get('row_count'),
            'pg_last_modified': pg_schema.get(table, {}).get('last_modified'),
            'mdb_detail': mdb_schema.get(table),
            'pg_detail': pg_schema.get(table)
        }
    
    return comparison

if __name__ == '__main__':
    print("Extracting MDB schema...")
    mdb_schema = extract_mdb_schema()
    print(f"✓ Found {len(mdb_schema)} tables in MDB")
    
    print("\nExtracting PostgreSQL schema...")
    pg_schema = get_postgres_schema()
    print(f"✓ Found {len(pg_schema)} tables in PostgreSQL")
    
    print("\nComparing schemas...")
    comparison = compare_schemas(mdb_schema, pg_schema)
    
    # Save to JSON
    output_file = r"L:\limo\reports\schema_comparison_2025-12-26.json"
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(comparison, f, indent=2, default=str)
    
    print(f"✓ Saved to {output_file}")
    
    # Print summary
    print("\n" + "="*60)
    print("SCHEMA COMPARISON SUMMARY")
    print("="*60)
    print(f"MDB Tables: {comparison['mdb_tables']}")
    print(f"PostgreSQL Tables: {comparison['pg_tables']}")
    
    missing = [t for t, v in comparison['tables'].items() if v['in_mdb'] and not v['in_pg']]
    added = [t for t, v in comparison['tables'].items() if not v['in_mdb'] and v['in_pg']]
    modified = [t for t, v in comparison['tables'].items() if v['columns_added'] or v['columns_removed']]
    
    print(f"\nTables in MDB but NOT in PostgreSQL: {len(missing)}")
    if missing:
        for t in missing[:10]:
            print(f"  - {t}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    
    print(f"\nTables in PostgreSQL but NOT in MDB: {len(added)}")
    if added:
        for t in added[:10]:
            print(f"  - {t}")
        if len(added) > 10:
            print(f"  ... and {len(added) - 10} more")
    
    print(f"\nTables with structural changes: {len(modified)}")
    if modified:
        for t in modified[:10]:
            detail = comparison['tables'][t]
            if detail['columns_added']:
                print(f"  - {t}: +{len(detail['columns_added'])} columns")
            if detail['columns_removed']:
                print(f"  - {t}: -{len(detail['columns_removed'])} columns")
        if len(modified) > 10:
            print(f"  ... and {len(modified) - 10} more")
