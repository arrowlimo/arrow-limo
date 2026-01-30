#!/usr/bin/env python3
"""
Load authoritative reserve/client/date relationships from legacy LMS.mdb database.

This extracts the source of truth for what reserves should exist.
"""
import pyodbc
import os
from decimal import Decimal
from datetime import datetime

LMS_DB = r"L:\limo\data\lms.mdb"

def main():
    try:
        # List available ODBC drivers first
        print("Available ODBC drivers:")
        for driver in pyodbc.drivers():
            print(f"  {driver}")
        print()
        
        # Connect to Access database - try different driver names
        driver_names = [
            "Microsoft Access Driver (*.mdb, *.accdb)",
            "Microsoft Access Driver (*.mdb)",
            "Microsoft Access ODBC Driver"
        ]
        
        conn = None
        for driver_name in driver_names:
            try:
                conn_str = f"Driver={{{driver_name}}};DBQ={LMS_DB}"
                print(f"Trying: {driver_name}...")
                conn = pyodbc.connect(conn_str)
                print(f"SUCCESS with {driver_name}")
                break
            except Exception as e:
                print(f"  Failed: {e}")
                continue
        
        if not conn:
            raise Exception("Could not connect to LMS database with any available driver")
        cur = conn.cursor()
        
        # List all tables in LMS database - skip MSysObjects, use Table_List
        print("=" * 80)
        print("LEGACY LMS DATABASE STRUCTURE")
        print("=" * 80)
        print("\nScanning for Reserve/Charter tables...")
        
        # Try common table names
        table_names_to_try = ['Reserve', 'Reserves', 'Reservation', 'Reservations', 
                              'Charter', 'Charters', 'tblReserve', 'tblCharter',
                              'tblCharters', 'tblReserves', 'tblReservation']
        
        found_tables = []
        for table_name in table_names_to_try:
            try:
                cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                count = cur.fetchone()[0]
                print(f"\nFound table: {table_name} ({count:,} rows)")
                found_tables.append(table_name)
                
                # Get column names and sample
                cur.execute(f"SELECT TOP 5 * FROM [{table_name}]")
                columns = [desc[0] for desc in cur.description]
                print(f"  Columns ({len(columns)}): {', '.join(columns[:15])}")
                
                rows = cur.fetchall()
                if rows:
                    print(f"  Sample row 1: {rows[0][:8]}")
                    
            except Exception as e:
                pass
        
        if not found_tables:
            print("\nNo standard table names found. Trying generic approach...")
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
