#!/usr/bin/env python3
"""
Inspect LMS Access Database Structure
"""
import pyodbc
import os

LMS_PATH = r"L:\limo\lms.mdb"

def get_lms_conn():
    """Connect to LMS Access database via ODBC"""
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={LMS_PATH};'
    return pyodbc.connect(conn_str)

def inspect_tables():
    """Inspect all tables and their columns in LMS database"""
    print("=== LMS Database Structure ===")
    
    try:
        with get_lms_conn() as conn:
            cur = conn.cursor()
            
            # Get all tables
            tables = []
            for table_info in cur.tables(tableType='TABLE'):
                tables.append(table_info.table_name)
            
            print(f"Found {len(tables)} tables:")
            for table in sorted(tables):
                print(f"  - {table}")
            
            print("\n" + "="*50)
            
            # Inspect each table structure
            for table_name in sorted(tables):
                if table_name.startswith('MSys'):  # Skip system tables
                    continue
                    
                print(f"\nTable: {table_name}")
                print("-" * (len(table_name) + 7))
                
                try:
                    # Get column info
                    columns = cur.columns(table=table_name)
                    col_info = []
                    for col in columns:
                        col_info.append((col.column_name, col.type_name))
                    
                    if col_info:
                        print("Columns:")
                        for col_name, col_type in col_info:
                            print(f"  {col_name} ({col_type})")
                        
                        # Get sample data (first 3 rows)
                        try:
                            cur.execute(f"SELECT TOP 3 * FROM [{table_name}]")
                            rows = cur.fetchall()
                            if rows:
                                print(f"\nSample data ({len(rows)} rows):")
                                col_names = [desc[0] for desc in cur.description]
                                for i, row in enumerate(rows):
                                    print(f"  Row {i+1}:")
                                    for j, value in enumerate(row):
                                        if j < len(col_names):
                                            print(f"    {col_names[j]}: {value}")
                        except Exception as e:
                            print(f"  Could not read sample data: {e}")
                    else:
                        print("  No columns found")
                        
                except Exception as e:
                    print(f"  Error inspecting table: {e}")
                
                print()
                
    except Exception as e:
        print(f"Error connecting to LMS database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    inspect_tables()