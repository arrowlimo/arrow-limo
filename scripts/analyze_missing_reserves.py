#!/usr/bin/env python3
"""
Check the 66 missing reserves in LMS - their dates and client details.
Determine if they're recent (Jan 2026) or from historical data.
"""
import pyodbc
import psycopg2
import os
from datetime import datetime

LMS_DB = r"L:\limo\data\lms.mdb"
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def main():
    try:
        # Load all LMS reserves
        lms_conn_str = "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + LMS_DB
        lms_conn = pyodbc.connect(lms_conn_str)
        lms_cur = lms_conn.cursor()
        
        lms_cur.execute("SELECT Reserve_No, Name, PU_Date FROM Reserve WHERE Reserve_No IS NOT NULL ORDER BY Reserve_No")
        lms_reserves = {}
        for row in lms_cur.fetchall():
            res_no = str(row[0]).strip()
            client = str(row[1]).strip() if row[1] else ""
            pu_date = row[2]
            lms_reserves[res_no] = (client, pu_date)
        
        # Get database reserves
        conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password=DB_PASSWORD)
        cur = conn.cursor()
        
        cur.execute("SELECT DISTINCT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
        db_reserves = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()
        
        # Find missing
        missing = set(lms_reserves.keys()) - db_reserves
        missing_sorted = sorted(missing)
        
        print("=" * 100)
        print("MISSING 66 RESERVES FROM DATABASE - DETAILED ANALYSIS")
        print("=" * 100)
        print(f"\nReserve | Client Name                | PU_Date (Pickup)        | Order_Date (Booked)     | Age")
        print("-" * 100)
        
        # Load full details for missing reserves
        lms_cur.execute("SELECT TOP 1000 Reserve_No, Name, PU_Date, Order_Date FROM Reserve WHERE Reserve_No IS NOT NULL ORDER BY Reserve_No")
        all_lms_data = {str(row[0]).strip(): (str(row[1]).strip() if row[1] else "", row[2], row[3]) for row in lms_cur.fetchall()}
        
        missing_details = []
        for res_no in missing_sorted:
            if res_no in all_lms_data:
                client, pu_date, order_date = all_lms_data[res_no]
                missing_details.append({
                    'reserve': res_no,
                    'client': client or "NULL",
                    'pu_date': pu_date,
                    'order_date': order_date
                })
        
        # Display all missing reserves
        for detail in missing_details:
            res = detail['reserve']
            client = detail['client'][:28] if detail['client'] else "NULL"
            pu = detail['pu_date'] if detail['pu_date'] else "NULL"
            order = detail['order_date'] if detail['order_date'] else "NULL"
            
            # Calculate age
            if detail['pu_date']:
                age_days = (datetime.now().date() - detail['pu_date'].date()).days if hasattr(detail['pu_date'], 'date') else (datetime.now().date() - detail['pu_date']).days
                age_label = f"{age_days} days ago"
            else:
                age_label = "N/A"
            
            print(f"{res:<7} | {client:<28} | {str(pu):<25} | {str(order):<25} | {age_label:<20}")
        
        # Summary statistics
        lms_conn.close()
        
        print("\n" + "=" * 100)
        print("ANALYSIS")
        print("=" * 100)
        
        # Categorize by date
        recent_2026 = [d for d in missing_details if d['pu_date'] and d['pu_date'].year == 2026]
        recent_2025 = [d for d in missing_details if d['pu_date'] and d['pu_date'].year == 2025]
        older = [d for d in missing_details if d['pu_date'] and d['pu_date'].year < 2025]
        
        print(f"\nBy pickup date year:")
        print(f"  2026 (Jan-present):  {len(recent_2026):>3} reserves - RECENT, possibly not imported yet")
        print(f"  2025:                {len(recent_2025):>3} reserves - Last year")
        print(f"  Before 2025:         {len(older):>3} reserves - Historical data")
        
        if recent_2026:
            print(f"\nRecent 2026 reserves not yet imported:")
            for detail in sorted(recent_2026, key=lambda x: x['pu_date']):
                print(f"  {detail['reserve']:<7} {detail['client']:<30} {detail['pu_date']}")
        
        if recent_2025:
            print(f"\n2025 reserves not in database:")
            for detail in sorted(recent_2025, key=lambda x: x['pu_date'])[:5]:
                print(f"  {detail['reserve']:<7} {detail['client']:<30} {detail['pu_date']}")
            if len(recent_2025) > 5:
                print(f"  ... and {len(recent_2025)-5} more")
        
        # Check if there's a date cutoff
        print(f"\n" + "=" * 100)
        print("IMPORT CUTOFF ANALYSIS")
        print("=" * 100)
        
        if missing_details:
            earliest_missing = min(missing_details, key=lambda x: x['pu_date'] if x['pu_date'] else datetime.max.date())
            latest_missing = max(missing_details, key=lambda x: x['pu_date'] if x['pu_date'] else datetime.min.date())
            
            print(f"\nEarliest missing PU_Date: {earliest_missing['pu_date']} (Reserve {earliest_missing['reserve']})")
            print(f"Latest missing PU_Date:   {latest_missing['pu_date']} (Reserve {latest_missing['reserve']})")
            
            # Find where database cutoff is
            conn = psycopg2.connect(host="localhost", dbname="almsdata", user="postgres", password=DB_PASSWORD)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT MAX(charter_date) FROM charters
                WHERE reserve_number IN (
                    SELECT DISTINCT reserve_number FROM charters
                    WHERE reserve_number >= '019000' AND reserve_number <= '020000'
                )
            """)
            result = cur.fetchone()
            cutoff_date = result[0] if result[0] else None
            
            print(f"\nDatabase cutoff (19xxx reserves): {cutoff_date}")
            print(f"\nConclusion:")
            if len(recent_2026) > 0:
                print(f"  - {len(recent_2026)} missing reserves are from 2026 (recent, likely not imported yet)")
                print(f"  - These can be imported when new data is available")
            if len(recent_2025) > 0:
                print(f"  - {len(recent_2025)} missing reserves are from 2025 (should investigate)")
                print(f"  - These may have been filtered out during import or are new additions to LMS")
            
            cur.close()
            conn.close()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
