"""
Verify driver, vehicle, and client name matches between LMS staging and ALMS
- Leave as nil if LMS has no data
- Match client_name from blended column
- Uses LMS staging table (lms2026_reserves) compared to charters
"""

import os
import psycopg2

# ALMS PostgreSQL connection
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

def get_lms_charter_details():
    """Get driver_code, vehicle_code, client from LMS staging"""
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    query = """
    SELECT 
        reserve_no,
        driver_code,
        vehicle_code,
        client_name
    FROM lms2026_reserves
    WHERE reserve_no IS NOT NULL
    ORDER BY reserve_no
    """
    
    pg_cur.execute(query)
    
    lms_data = {}
    for row in pg_cur:
        reserve_no = row[0].strip() if row[0] else None
        if reserve_no:
            lms_data[reserve_no] = {
                'driver': row[1].strip() if row[1] else None,
                'vehicle': row[2].strip() if row[2] else None,
                'client': row[3].strip() if row[3] else None
            }
    
    pg_cur.close()
    pg_conn.close()
    
    return lms_data

def get_alms_charter_details():
    """Get driver_code, vehicle_number, client_name from ALMS charters"""
    pg_conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    pg_cur = pg_conn.cursor()
    
    query = """
    SELECT 
        c.reserve_number,
        e.driver_code,
        v.vehicle_number,
        c.client_display_name
    FROM charters c
    LEFT JOIN employees e ON c.assigned_driver_id = e.employee_id
    LEFT JOIN vehicles v ON c.vehicle_id = v.vehicle_id
    WHERE c.reserve_number IS NOT NULL
    ORDER BY c.reserve_number
    """
    
    pg_cur.execute(query)
    
    alms_data = {}
    for row in pg_cur:
        reserve_no = row[0].strip() if row[0] else None
        if reserve_no:
            alms_data[reserve_no] = {
                'driver': row[1].strip() if row[1] else None,
                'vehicle': row[2].strip() if row[2] else None,
                'client_name': row[3].strip() if row[3] else None
            }
    
    pg_cur.close()
    pg_conn.close()
    
    return alms_data

def compare_data():
    """Compare LMS and ALMS data"""
    print("Fetching LMS data...")
    lms_data = get_lms_charter_details()
    print(f"✅ Found {len(lms_data)} charters in LMS\n")
    
    print("Fetching ALMS data...")
    alms_data = get_alms_charter_details()
    print(f"✅ Found {len(alms_data)} charters in ALMS\n")
    
    # Find common reserve numbers
    common_reserves = set(lms_data.keys()) & set(alms_data.keys())
    print(f"Comparing {len(common_reserves)} common charters...\n")
    
    # Track matches and mismatches
    driver_matches = 0
    driver_mismatches = []
    driver_lms_null = 0
    
    vehicle_matches = 0
    vehicle_mismatches = []
    vehicle_lms_null = 0
    
    client_matches = 0
    client_mismatches = []
    client_lms_null = 0
    
    for reserve_no in sorted(common_reserves):
        lms = lms_data[reserve_no]
        alms = alms_data[reserve_no]
        
        # Driver comparison
        if lms['driver'] is None:
            driver_lms_null += 1
        elif lms['driver'] == alms['driver']:
            driver_matches += 1
        else:
            driver_mismatches.append({
                'reserve': reserve_no,
                'lms': lms['driver'],
                'alms': alms['driver']
            })
        
        # Vehicle comparison
        if lms['vehicle'] is None:
            vehicle_lms_null += 1
        elif lms['vehicle'] == alms['vehicle']:
            vehicle_matches += 1
        else:
            vehicle_mismatches.append({
                'reserve': reserve_no,
                'lms': lms['vehicle'],
                'alms': alms['vehicle']
            })
        
        # Client comparison
        if lms['client'] is None:
            client_lms_null += 1
        elif lms['client'] == alms['client_name']:
            client_matches += 1
        else:
            client_mismatches.append({
                'reserve': reserve_no,
                'lms': lms['client'],
                'alms': alms['client_name']
            })
    
    # Print results
    print("=" * 80)
    print("DRIVER VERIFICATION")
    print("=" * 80)
    print(f"✅ Matches: {driver_matches}")
    print(f"⚪ LMS NULL (left as nil): {driver_lms_null}")
    print(f"❌ Mismatches: {len(driver_mismatches)}")
    
    if driver_mismatches:
        print("\nDriver Mismatches (first 20):")
        for item in driver_mismatches[:20]:
            print(f"  {item['reserve']}: LMS='{item['lms']}' vs ALMS='{item['alms']}'")
    
    print("\n" + "=" * 80)
    print("VEHICLE VERIFICATION")
    print("=" * 80)
    print(f"✅ Matches: {vehicle_matches}")
    print(f"⚪ LMS NULL (left as nil): {vehicle_lms_null}")
    print(f"❌ Mismatches: {len(vehicle_mismatches)}")
    
    if vehicle_mismatches:
        print("\nVehicle Mismatches (first 20):")
        for item in vehicle_mismatches[:20]:
            print(f"  {item['reserve']}: LMS='{item['lms']}' vs ALMS='{item['alms']}'")
    
    print("\n" + "=" * 80)
    print("CLIENT NAME VERIFICATION")
    print("=" * 80)
    print(f"✅ Matches: {client_matches}")
    print(f"⚪ LMS NULL (left as nil): {client_lms_null}")
    print(f"❌ Mismatches: {len(client_mismatches)}")
    
    if client_mismatches:
        print("\nClient Name Mismatches (first 20):")
        for item in client_mismatches[:20]:
            print(f"  {item['reserve']}: LMS='{item['lms']}' vs ALMS='{item['alms']}'")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_comparisons = len(common_reserves)
    driver_pct = (driver_matches / total_comparisons * 100) if total_comparisons > 0 else 0
    vehicle_pct = (vehicle_matches / total_comparisons * 100) if total_comparisons > 0 else 0
    client_pct = (client_matches / total_comparisons * 100) if total_comparisons > 0 else 0
    
    print(f"Driver Match Rate: {driver_pct:.1f}% ({driver_matches}/{total_comparisons})")
    print(f"Vehicle Match Rate: {vehicle_pct:.1f}% ({vehicle_matches}/{total_comparisons})")
    print(f"Client Match Rate: {client_pct:.1f}% ({client_matches}/{total_comparisons})")
    
    # Recommendation
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    
    if len(driver_mismatches) > 100 or len(vehicle_mismatches) > 100 or len(client_mismatches) > 100:
        print("⚠️  SIGNIFICANT MISMATCHES FOUND")
        print("Review mismatches before proceeding with bulk import.")
        print("\nPossible causes:")
        print("- Name format differences (e.g., 'John Smith' vs 'Smith, John')")
        print("- Abbreviations (e.g., 'Vehicle #1' vs 'VEH1')")
        print("- Data entry errors in LMS or ALMS")
    else:
        print("✅ Match rates acceptable for import")
        print("Minor mismatches can be reviewed and corrected post-import.")

if __name__ == "__main__":
    compare_data()
