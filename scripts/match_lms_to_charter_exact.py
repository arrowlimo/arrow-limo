#!/usr/bin/env python3
"""
Match exact charter date/client relationship between legacy LMS and almsdata.

This is the source of truth for which charters are real vs. spurious.
"""
import pyodbc
import psycopg2
import os
from datetime import datetime

LMS_DB = r"L:\limo\data\lms.mdb"
DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_lms_charter_data():
    """Load reserve/client/date from authoritative LMS source."""
    conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    # Get all reserves with valid data from LMS
    cur.execute("""
        SELECT Reserve_No, Name, PU_Date
        FROM Reserve
        WHERE Reserve_No IS NOT NULL
        ORDER BY Reserve_No
    """)
    
    lms_data = {}
    for row in cur.fetchall():
        res_no = str(row[0]).strip() if row[0] else None
        client_name = str(row[1]).strip() if row[1] else None
        pu_date = row[2]
        
        if res_no:
            lms_data[res_no] = {
                'client': client_name,
                'date': pu_date
            }
    
    conn.close()
    return lms_data

def normalize_client_name(name):
    """Normalize client name for comparison."""
    if not name:
        return None
    name = str(name).strip().lower()
    # Remove extra spaces, standardize abbreviations
    name = ' '.join(name.split())
    return name

def main():
    try:
        print("=" * 100)
        print("AUTHORITATIVE CHARTER COMPARISON: LMS vs. almsdata")
        print("=" * 100)
        
        # Load LMS data
        print("\nLoading legacy LMS authoritative data...")
        lms_data = get_lms_charter_data()
        print(f"✓ Loaded {len(lms_data):,} reserves from LMS")
        
        # Connect to almsdata
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Get all charters from almsdata
        print("Loading current database charters...")
        cur.execute("""
            SELECT c.reserve_number, cl.name as client_name, c.charter_date
            FROM charters c
            LEFT JOIN clients cl ON cl.client_id = c.client_id
            ORDER BY c.reserve_number
        """)
        
        db_charters = {}
        for row in cur.fetchall():
            res_num = str(row[0]).strip() if row[0] else None
            client = row[1]
            charter_date = row[2]
            
            if res_num:
                db_charters[res_num] = {
                    'client': client,
                    'date': charter_date
                }
        
        print(f"✓ Loaded {len(db_charters):,} charters from almsdata")
        
        # Compare
        print("\n" + "=" * 100)
        print("MATCHING ANALYSIS")
        print("=" * 100)
        
        exact_matches = 0
        client_mismatch_only = 0
        date_mismatch_only = 0
        both_mismatch = 0
        spurious_in_db = 0
        missing_from_db = 0
        
        mismatches = []
        
        # Check each database charter against LMS
        for res_num in sorted(db_charters.keys()):
            db_info = db_charters[res_num]
            
            if res_num in lms_data:
                lms_info = lms_data[res_num]
                
                # Normalize names for comparison
                db_client_norm = normalize_client_name(db_info['client'])
                lms_client_norm = normalize_client_name(lms_info['client'])
                
                client_match = (db_client_norm == lms_client_norm)
                date_match = (db_info['date'] == lms_info['date'])
                
                if client_match and date_match:
                    exact_matches += 1
                elif client_match and not date_match:
                    date_mismatch_only += 1
                    mismatches.append((res_num, 'DATE_ONLY', db_info, lms_info))
                elif not client_match and date_match:
                    client_mismatch_only += 1
                    mismatches.append((res_num, 'CLIENT_ONLY', db_info, lms_info))
                else:
                    both_mismatch += 1
                    mismatches.append((res_num, 'BOTH', db_info, lms_info))
            else:
                spurious_in_db += 1
        
        # Check for LMS reserves missing from DB
        for res_num in lms_data.keys():
            if res_num not in db_charters:
                missing_from_db += 1
        
        print(f"\nExact matches (date + client):    {exact_matches:>6,} ({100*exact_matches/len(db_charters):.1f}%)")
        print(f"Date mismatch only:               {date_mismatch_only:>6,}")
        print(f"Client mismatch only:             {client_mismatch_only:>6,}")
        print(f"Both date + client mismatch:      {both_mismatch:>6,}")
        print(f"Spurious reserves (NOT in LMS):   {spurious_in_db:>6,}")
        print(f"Reserves missing from DB:         {missing_from_db:>6,}")
        
        total_mismatched = client_mismatch_only + date_mismatch_only + both_mismatch + spurious_in_db
        print(f"\nTOTAL PROBLEMS:                   {total_mismatched:>6,} ({100*total_mismatched/len(db_charters):.1f}%)")
        print(f"TOTAL IN LMS:                     {len(lms_data):>6,}")
        print(f"TOTAL IN DATABASE:                {len(db_charters):>6,}")
        
        # Show mismatches
        if mismatches:
            print(f"\n{'MISMATCHED CHARTERS (sample of 30):':<60}")
            print("-" * 100)
            print(f"{'Reserve':<10} {'Type':<15} {'DB Client':<30} {'LMS Client':<30}")
            print("-" * 100)
            for res_num, mtype, db_info, lms_info in mismatches[:30]:
                db_c = (db_info['client'] or 'NULL')[:29]
                lms_c = (lms_info['client'] or 'NULL')[:29]
                print(f"{res_num:<10} {mtype:<15} {db_c:<30} {lms_c:<30}")
        
        # Show spurious reserves
        spurious = []
        for res_num in db_charters.keys():
            if res_num not in lms_data:
                spurious.append(res_num)
        
        if spurious:
            print(f"\n{'SPURIOUS RESERVES IN DATABASE (NOT IN LMS):':<60}")
            print(f"Total: {len(spurious):,} reserves don't exist in legacy LMS")
            print(f"Sample (first 30): {', '.join(sorted(spurious)[:30])}")
            
            # Show date range of spurious
            cur.execute("""
                SELECT MIN(charter_date), MAX(charter_date)
                FROM charters
                WHERE reserve_number IN ({})
            """.format(','.join([f"'{r}'" for r in spurious[:100]])))  # Sample
            
            result = cur.fetchone()
            if result[0]:
                print(f"Date range (sample): {result[0]} to {result[1]}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 100)
        print("CONCLUSION")
        print("=" * 100)
        if exact_matches == len(db_charters):
            print("\n✓ All database charters match LMS (date + client)")
        else:
            print(f"\n✗ Only {exact_matches:,} of {len(db_charters):,} charters match LMS exactly")
            print(f"  {total_mismatched:,} charters have data integrity issues")
            print(f"  {spurious_in_db:,} charters are completely spurious (not in LMS)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
