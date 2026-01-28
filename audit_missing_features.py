import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
tables = [row[0] for row in cur.fetchall()]

keywords = {
    'Vehicle Maintenance': ['maintenance', 'repair', 'service', 'scheduled'],
    'Inspections/CVIP': ['inspection', 'cvip', 'pre_trip', 'vehicle_check'],
    'Vehicle Lifecycle': ['purchase', 'sale', 'writeoff', 'write_off', 'repossession'],
    'Mileage': ['mileage', 'odometer', 'fuel_log', 'distance'],
    'Driver App': ['mobile', 'driver_app', 'driver_portal'],
    'Driver Notes': ['driver_notes', 'driver_warnings', 'internal_notes'],
    'HOS': ['hours_of_service', 'hos', 'duty'],
    'Vehicle Condition': ['condition', 'pre_inspection', 'damage', 'incident']
}

print("\n" + "="*80)
print("ARROW LIMOUSINE SYSTEM - FEATURE AUDIT")
print("="*80)

found_tables = {category: [] for category in keywords}

for category, search_terms in keywords.items():
    for table in tables:
        for term in search_terms:
            if term in table.lower():
                found_tables[category].append(table)
                break

for category, found in found_tables.items():
    status = "✅" if found else "❌"
    print(f"\n{status} {category}:")
    if found:
        for table in sorted(set(found)):
            print(f"   - {table}")
    else:
        print(f"   [MISSING - No tables found]")

print(f"\n{'='*80}")
print("VEHICLES TABLE COLUMNS (for context):")
print('='*80)
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'vehicles'
    ORDER BY ordinal_position
""")
for col, dtype in cur.fetchall():
    print(f"  {col:<30} {dtype}")

cur.close()
conn.close()
