#!/usr/bin/env python
"""
Verify key tables from MDB backup against PostgreSQL almsdata
Focus on: charters, payments, drivers, vehicles, etc.
"""
import pyodbc
import psycopg2
import json
from datetime import datetime

def get_key_tables():
    """List of critical tables to verify"""
    return [
        'charters', 'payments', 'drivers', 'vehicles', 'employees',
        'receipts', 'banking_transactions', 'payment_methods',
        'customers', 'routes', 'driver_payments', 'vehicle_maintenance'
    ]

def extract_mdb_data():
    """Extract key data from MDB"""
    mdb_path = r"L:\limo\backups\lms.mdb"
    data = {}
    
    try:
        conn_str = f'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};'
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        # Get all tables from MDB
        for table_info in cursor.tables(tableType='TABLE'):
            table_name = table_info[2]
            
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                count = cursor.fetchone()[0]
                
                # Get columns
                cols_cursor = cursor.columns(table=table_name)
                columns = [col[3] for col in cols_cursor]
                
                data[table_name] = {
                    'row_count': count,
                    'columns': columns,
                    'column_count': len(columns)
                }
            except:
                pass
        
        conn.close()
        return data
    except Exception as e:
        print(f"Error reading MDB: {e}")
        return {}

def extract_pg_data():
    """Extract key data from PostgreSQL"""
    data = {}
    
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="almsdata",
            user="postgres",
            password="***REMOVED***"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        for table_name, in cursor.fetchall():
            try:
                cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                count = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}'
                    ORDER BY ordinal_position
                """)
                columns = [row[0] for row in cursor.fetchall()]
                
                data[table_name] = {
                    'row_count': count,
                    'columns': columns,
                    'column_count': len(columns)
                }
            except:
                pass
        
        conn.close()
        return data
    except Exception as e:
        print(f"Error reading PostgreSQL: {e}")
        return {}

def verify_critical_tables(mdb_data, pg_data):
    """Verify critical tables exist and have data"""
    critical = get_key_tables()
    results = {
        'timestamp': datetime.now().isoformat(),
        'verified_tables': {},
        'missing_in_pg': [],
        'missing_in_mdb': [],
        'data_mismatches': []
    }
    
    for table in critical:
        # Check if exists in MDB
        in_mdb = any(t.lower() == table.lower() for t in mdb_data.keys())
        mdb_table = next((t for t in mdb_data.keys() if t.lower() == table.lower()), None)
        
        # Check if exists in PG
        in_pg = any(t.lower() == table.lower() for t in pg_data.keys())
        pg_table = next((t for t in pg_data.keys() if t.lower() == table.lower()), None)
        
        results['verified_tables'][table] = {
            'in_mdb': in_mdb,
            'in_pg': in_pg,
            'mdb_rows': mdb_data[mdb_table]['row_count'] if mdb_table else 0,
            'pg_rows': pg_data[pg_table]['row_count'] if pg_table else 0,
            'mdb_columns': mdb_data[mdb_table]['column_count'] if mdb_table else 0,
            'pg_columns': pg_data[pg_table]['column_count'] if pg_table else 0,
        }
        
        if in_mdb and not in_pg:
            results['missing_in_pg'].append(table)
        elif in_pg and not in_mdb:
            results['missing_in_mdb'].append(table)
        
        if in_mdb and in_pg:
            mdb_rows = mdb_data[mdb_table]['row_count']
            pg_rows = pg_data[pg_table]['row_count']
            if mdb_rows != pg_rows:
                results['data_mismatches'].append({
                    'table': table,
                    'mdb_rows': mdb_rows,
                    'pg_rows': pg_rows,
                    'difference': pg_rows - mdb_rows
                })
    
    return results

if __name__ == '__main__':
    print("="*70)
    print("CRITICAL TABLES VERIFICATION REPORT")
    print("MDB Backup (lms.mdb) vs PostgreSQL (almsdata)")
    print("="*70)
    
    print("\nExtracting MDB data...")
    mdb_data = extract_mdb_data()
    print(f"✓ Found {len(mdb_data)} tables in MDB")
    
    print("Extracting PostgreSQL data...")
    pg_data = extract_pg_data()
    print(f"✓ Found {len(pg_data)} tables in PostgreSQL")
    
    print("\nVerifying critical tables...")
    results = verify_critical_tables(mdb_data, pg_data)
    
    # Save full report
    output_file = r"L:\limo\reports\critical_tables_verification.json"
    with open(output_file, 'w') as f:
        json.dump({**results, 'full_mdb_inventory': mdb_data, 'full_pg_inventory': pg_data}, f, indent=2, default=str)
    print(f"✓ Full report saved to {output_file}")
    
    # Print summary
    print("\n" + "="*70)
    print("CRITICAL TABLES STATUS")
    print("="*70)
    for table, status in results['verified_tables'].items():
        in_both = status['in_mdb'] and status['in_pg']
        symbol = "✓" if in_both else "⚠"
        print(f"{symbol} {table:20} | MDB: {status['mdb_rows']:6} rows | PG: {status['pg_rows']:6} rows")
    
    print("\n" + "="*70)
    if results['missing_in_pg']:
        print(f"⚠ MISSING IN POSTGRESQL ({len(results['missing_in_pg'])}):")
        for table in results['missing_in_pg']:
            print(f"  - {table}")
    
    if results['missing_in_mdb']:
        print(f"ℹ ADDED IN POSTGRESQL ({len(results['missing_in_mdb'])}):")
        for table in results['missing_in_mdb']:
            print(f"  + {table}")
    
    if results['data_mismatches']:
        print(f"\n⚠ DATA MISMATCHES ({len(results['data_mismatches'])}):")
        for mismatch in results['data_mismatches']:
            diff = mismatch['difference']
            symbol = "+" if diff > 0 else "-"
            print(f"  {mismatch['table']:20} | PG has {symbol}{abs(diff)} rows")
    
    print("\n" + "="*70)
