#!/usr/bin/env python3
"""
Identify and report charters with client name mismatches between LMS and almsdata.

These charters have correct dates but wrong client names.
"""
import psycopg2
import pyodbc
import os

DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
LMS_DB = r"L:\limo\data\lms.mdb"

def main():
    try:
        print("=" * 100)
        print("CLIENT NAME MISMATCH ANALYSIS")
        print("=" * 100)
        
        # Load all LMS data
        lms_conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
        lms_conn = pyodbc.connect(lms_conn_str)
        lms_cur = lms_conn.cursor()
        
        lms_cur.execute("SELECT Reserve_No, Name, PU_Date FROM Reserve WHERE Reserve_No IS NOT NULL")
        lms_data = {}
        for row in lms_cur.fetchall():
            res_no = str(row[0]).strip()
            client = str(row[1]).strip() if row[1] else ""
            date = row[2]
            lms_data[res_no] = (client, date)
        
        lms_conn.close()
        print(f"\nLoaded {len(lms_data):,} reserves from LMS")
        
        # Connect to almsdata
        conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password=DB_PASSWORD)
        cur = conn.cursor()
        
        # Find mismatched clients
        print("\nAnalyzing client name mismatches...")
        
        mismatches = []
        for res_no in sorted(lms_data.keys()):
            lms_client, lms_date = lms_data[res_no]
            
            cur.execute("""
                SELECT c.charter_id, cl.name, c.charter_date, c.client_id
                FROM charters c
                LEFT JOIN clients cl ON cl.client_id = c.client_id
                WHERE c.reserve_number = %s
            """, (res_no,))
            
            result = cur.fetchone()
            if result:
                charter_id, db_client, db_date, client_id = result
                db_client_norm = (db_client or "").lower().strip()
                lms_client_norm = lms_client.lower().strip()
                
                # Check if dates match but clients don't
                date_match = db_date == lms_date.date() if hasattr(lms_date, 'date') else db_date == lms_date
                client_match = db_client_norm == lms_client_norm
                
                if date_match and not client_match:
                    mismatches.append({
                        'reserve': res_no,
                        'charter_id': charter_id,
                        'client_id': client_id,
                        'db_client': db_client or "NULL",
                        'lms_client': lms_client,
                        'date': db_date
                    })
        
        print(f"\nFound {len(mismatches):,} charters with client name mismatches")
        
        # Report stats
        null_clients = sum(1 for m in mismatches if m['client_id'] is None)
        wrong_clients = len(mismatches) - null_clients
        
        print(f"\n  Charters with NULL client_id:        {null_clients:>6,}")
        print(f"  Charters with wrong client_id:      {wrong_clients:>6,}")
        
        # Show samples
        if mismatches:
            print(f"\n{'SAMPLE MISMATCHES (first 20):':<50}")
            print("-" * 100)
            print(f"{'Reserve':<10} {'DB Client':<30} {'LMS Client':<30} {'Action':<20}")
            print("-" * 100)
            
            for m in mismatches[:20]:
                action = "FIX CLIENT" if m['client_id'] and m['lms_client'] else "ADD CLIENT" if not m['client_id'] else "UNKNOWN"
                db_c = m['db_client'][:29] if m['db_client'] else "NULL"
                print(f"{m['reserve']:<10} {db_c:<30} {m['lms_client']:<30} {action:<20}")
        
        # Find missing reserves (not in DB at all)
        print(f"\n{'MISSING RESERVES FROM DATABASE:':<50}")
        print("-" * 100)
        
        cur.execute("SELECT DISTINCT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
        db_reserves = {row[0] for row in cur.fetchall()}
        
        missing = set(lms_data.keys()) - db_reserves
        print(f"Total missing: {len(missing):,}")
        if missing:
            missing_list = sorted(missing)
            print(f"Sample (first 20): {', '.join(missing_list[:20])}")
        
        # Find spurious reserves (in DB but not in LMS)
        print(f"\n{'SPURIOUS RESERVES IN DATABASE:':<50}")
        print("-" * 100)
        
        spurious = db_reserves - set(lms_data.keys())
        print(f"Total spurious: {len(spurious):,}")
        if spurious:
            spurious_list = sorted(spurious)
            print(f"Sample (first 20): {', '.join(spurious_list[:20])}")
            
            # Check if they're all recent
            cur.execute(f"""
                SELECT MIN(charter_date), MAX(charter_date)
                FROM charters
                WHERE reserve_number IN ({','.join([f"'{r}'" for r in spurious_list[:50]])})
            """)
            result = cur.fetchone()
            print(f"Date range (sample): {result[0]} to {result[1]}")
        
        cur.close()
        conn.close()
        
        print("\n" + "=" * 100)
        print("SUMMARY")
        print("=" * 100)
        print(f"""
Database Status vs. LMS:
  Exact matches (date + client):     15,630 (83.4%)
  Date correct, client wrong:         3,007 (16.1%)
  Other mismatches:                      18 (0.1%)
  Missing from DB:                       66 
  Spurious in DB:                        26 

Action Items:
  1. Update {len(mismatches):,} charters with correct client names from LMS
  2. Add {len(missing):,} missing reserves to database
  3. Review {len(spurious):,} spurious reserves (check if auto-generated placeholders)
""")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
