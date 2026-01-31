#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Check LMS.mdb structure for Reserve, Vehicle, Driver tables and relationships
"""

import pyodbc
import sys

# Connect to LMS.mdb
try:
    conn_str = r'Driver={Microsoft Access Driver (*.mdb)};DBQ=L:\limo\backups\lms.mdb;'
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    print("=" * 80)
    print("LMS.MDB STRUCTURE ANALYSIS")
    print("=" * 80)
    
    # Get list of tables
    print("\n1. CHECKING RESERVE TABLE (Charters):")
    print("-" * 80)
    try:
        cur.execute("SELECT * FROM Reserve WHERE ID = 1")
        # Get column names
        col_names = [description[0] for description in cur.description]
        print(f"Columns in Reserve table: {len(col_names)}")
        for col in col_names:
            print(f"  - {col}")
    except Exception as e:
        print(f"Error reading Reserve: {e}")
    
    # Check Vehicle table
    print("\n2. CHECKING VEHICLE TABLE:")
    print("-" * 80)
    try:
        cur.execute("SELECT * FROM Vehicle WHERE ID = 1")
        col_names = [description[0] for description in cur.description]
        print(f"Columns in Vehicle table: {len(col_names)}")
        for col in col_names:
            print(f"  - {col}")
    except Exception as e:
        print(f"Error reading Vehicle: {e}")
    
    # Check Driver table
    print("\n3. CHECKING DRIVER TABLE:")
    print("-" * 80)
    try:
        cur.execute("SELECT * FROM Driver WHERE ID = 1")
        col_names = [description[0] for description in cur.description]
        print(f"Columns in Driver table: {len(col_names)}")
        for col in col_names:
            print(f"  - {col}")
    except Exception as e:
        print(f"Error reading Driver: {e}")
    
    # Check a sample reserve with all joins
    print("\n4. SAMPLE RESERVE DATA (with Vehicle & Driver lookups):")
    print("-" * 80)
    try:
        cur.execute("""
            SELECT TOP 5 
                r.ID, r.PU_Date, r.PU_Time,
                r.VehicleID, r.DriverID,
                r.Charge_Total
            FROM Reserve r
            ORDER BY r.PU_Date DESC
        """)
        rows = cur.fetchall()
        for row in rows:
            reserve_id, pu_date, pu_time, vehicle_id, driver_id, charge = row
            print(f"\nReserve ID: {reserve_id}")
            print(f"  Date: {pu_date}, Time: {pu_time}")
            print(f"  VehicleID: {vehicle_id}, DriverID: {driver_id}")
            print(f"  Charge: {charge}")
            
            # Try to fetch vehicle name
            if vehicle_id:
                try:
                    cur2 = conn.cursor()
                    cur2.execute("SELECT Vehicle_Number, Vehicle_Type FROM Vehicle WHERE ID = ?", (vehicle_id,))
                    v_row = cur2.fetchone()
                    if v_row:
                        print(f"  → Vehicle: {v_row[0]} ({v_row[1]})")
                    cur2.close()
                except:
                    pass
            
            # Try to fetch driver name
            if driver_id:
                try:
                    cur2 = conn.cursor()
                    cur2.execute("SELECT DriverName FROM Driver WHERE ID = ?", (driver_id,))
                    d_row = cur2.fetchone()
                    if d_row:
                        print(f"  → Driver: {d_row[0]}")
                    cur2.close()
                except:
                    pass
    except Exception as e:
        print(f"Error reading sample data: {e}")
    
    # Check 007032 specifically
    print("\n5. CHECKING RESERVE 007032 (if it exists):")
    print("-" * 80)
    try:
        cur.execute("SELECT * FROM Reserve WHERE ID = 7032 OR Reserve_Number = '007032'")
        row = cur.fetchone()
        if row:
            col_names = [description[0] for description in cur.description]
            print(f"Found reserve 007032!")
            for i, col in enumerate(col_names):
                print(f"  {col}: {row[i]}")
        else:
            print("Reserve 007032 not found in LMS.mdb")
    except Exception as e:
        print(f"Error: {e}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Cannot connect to LMS.mdb: {e}")
    sys.exit(1)
