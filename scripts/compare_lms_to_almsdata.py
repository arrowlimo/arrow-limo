#!/usr/bin/env python3
"""
Extract authoritative reserve/client/date from legacy LMS and compare to almsdata.

This identifies which charters are mismatched or spurious.
"""
import pyodbc
import psycopg2
import os
from datetime import datetime
from decimal import Decimal

LMS_DB = r"L:\limo\data\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_lms_data():
    """Load authoritative reserve/client/date data from legacy LMS."""
    conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    # Get Reserve table - extract key fields
    cur.execute("""
        SELECT Account_No, Bill_Name, Arrived
        FROM Reserve
        ORDER BY Account_No
    """)
    
    lms_data = {}
    for row in cur.fetchall():
        reserve_no = row[0].strip() if row[0] else None
        client_name = row[1].strip() if row[1] else None
        arrived_date = row[2]
        
        if reserve_no:
            lms_data[reserve_no] = {
                'client': client_name,
                'date': arrived_date
            }
    
    conn.close()
    return lms_data

def main():
    try:
        print("=" * 100)
        print("AUTHORITATIVE DATA COMPARISON: Legacy LMS vs. almsdata")
        print("=" * 100)
        
        # Load LMS data
        print("\nLoading legacy LMS reserve/client/date data...")
        lms_data = get_lms_data()
        print(f"  Loaded {len(lms_data):,} reserves from LMS")
        
        # Show sample
        sample_reserves = sorted(list(lms_data.keys()))[:10]
        print(f"\n  Sample LMS reserves (first 10):")
        for res in sample_reserves:
            info = lms_data[res]
            client = info['client'] or "UNKNOWN"
            date = info['date'] or "NULL"
            print(f"    {res:<8} Client: {client:<30} Date: {date}")
        
        # Connect to almsdata
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Get all charters from almsdata
        print("\n\nComparing to almsdata...")
        cur.execute("""
            SELECT c.reserve_number, cl.name as client_name, c.charter_date
            FROM charters c
            LEFT JOIN clients cl ON cl.client_id = c.client_id
            ORDER BY c.reserve_number
        """)
        
        db_charters = {}
        for row in cur.fetchall():
            res_num = row[0]
            client = row[1] or "NULL"
            charter_date = row[2]
            
            if res_num:
                db_charters[res_num] = {
                    'client': client,
                    'date': charter_date
                }
        
        print(f"  Loaded {len(db_charters):,} charters from almsdata")
        
        # Compare
        print("\n" + "=" * 100)
        print("COMPARISON RESULTS")
        print("=" * 100)
        
        # Charters that match LMS
        matching = 0
        client_mismatch = 0
        date_mismatch = 0
        reserve_only_in_db = 0
        reserve_only_in_lms = 0
        
        mismatched_charters = []
        
        for res_num in sorted(db_charters.keys()):
            db_info = db_charters[res_num]
            
            if res_num in lms_data:
                lms_info = lms_data[res_num]
                
                if (db_info['client'] == lms_info['client'] and 
                    db_info['date'] == lms_info['date']):
                    matching += 1
                else:
                    mismatch_details = []
                    if db_info['client'] != lms_info['client']:
                        client_mismatch += 1
                        mismatch_details.append(f"Client: '{db_info['client']}' vs '{lms_info['client']}'")
                    if db_info['date'] != lms_info['date']:
                        date_mismatch += 1
                        mismatch_details.append(f"Date: {db_info['date']} vs {lms_info['date']}")
                    
                    mismatched_charters.append((res_num, mismatch_details))
            else:
                reserve_only_in_db += 1
        
        # Count LMS reserves not in DB
        for res_num in lms_data.keys():
            if res_num not in db_charters:
                reserve_only_in_lms += 1
        
        print(f"\nMatching reserves (exact date + client): {matching:>6,}")
        print(f"Reserves with client mismatches:       {client_mismatch:>6,}")
        print(f"Reserves with date mismatches:         {date_mismatch:>6,}")
        print(f"Reserves ONLY in database:             {reserve_only_in_db:>6,}")
        print(f"Reserves ONLY in LMS (missing):        {reserve_only_in_lms:>6,}")
        print(f"\nTOTAL IN LMS:                          {len(lms_data):>6,}")
        print(f"TOTAL IN DATABASE:                     {len(db_charters):>6,}")
        
        # Show mismatches
        if mismatched_charters:
            print(f"\n{'MISMATCHED RESERVES (sample of 30):':<50}")
            print("-" * 100)
            for res_num, details in mismatched_charters[:30]:
                print(f"  {res_num:<8} → {', '.join(details)}")
        
        # Show reserves only in DB (spurious)
        spurious = []
        for res_num in db_charters.keys():
            if res_num not in lms_data:
                spurious.append(res_num)
        
        if spurious:
            print(f"\n{'SPURIOUS RESERVES IN DATABASE (NOT IN LMS):':<50}")
            print("-" * 100)
            print(f"Total spurious: {len(spurious):,}")
            print(f"Sample (first 20): {', '.join(sorted(spurious)[:20])}")
            
            # Check characteristics of spurious reserves
            print(f"\nSpurious reserve characteristics:")
            cur.execute(f"""
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT client_id) as unique_clients,
                    COUNT(DISTINCT charter_date) as unique_dates,
                    MIN(charter_date) as earliest_date,
                    MAX(charter_date) as latest_date
                FROM charters
                WHERE reserve_number NOT IN ({','.join([f"'{r}'" for r in sorted(lms_data.keys())])})
            """)
            row = cur.fetchone()
            print(f"  Total spurious charters: {row[0]:,}")
            print(f"  Unique client_ids: {row[1]:,}")
            print(f"  Date range: {row[3]} to {row[4]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
