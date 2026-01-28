import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

# Export vehicle_pricing_defaults
sql_file = f'l:\\limo\\exports\\vehicle_pricing_defaults_{timestamp}.sql'
os.makedirs(os.path.dirname(sql_file), exist_ok=True)

with open(sql_file, 'w') as f:
    f.write('-- Vehicle Pricing Defaults Export\n')
    f.write(f'-- Exported: {timestamp}\n')
    f.write('-- Note: Delete existing records before importing\n\n')
    
    f.write('DELETE FROM vehicle_pricing_defaults;\n\n')
    
    cur.execute(
        'SELECT vehicle_type, nrr, hourly_rate, daily_rate, standby_rate, '
        'airport_pickup_calgary, airport_pickup_edmonton, hourly_package, fee_1, fee_2, fee_3 '
        'FROM vehicle_pricing_defaults ORDER BY vehicle_type'
    )
    
    f.write('INSERT INTO vehicle_pricing_defaults '
            '(vehicle_type, nrr, hourly_rate, daily_rate, standby_rate, '
            'airport_pickup_calgary, airport_pickup_edmonton, hourly_package, fee_1, fee_2, fee_3) VALUES\n')
    
    rows = cur.fetchall()
    for i, row in enumerate(rows):
        vtype, nrr, hrate, drate, srate, calgary, edmonton, pkg, f1, f2, f3 = row
        pkg_val = f"'{pkg:.2f}'" if pkg else "NULL"
        values = (f"'{vtype}'", f"{nrr}", f"{hrate}", f"{drate}", f"{srate}", 
                  f"{calgary}", f"{edmonton}", pkg_val, f"{f1}", f"{f2}", f"{f3}")
        line = f"({', '.join(values)})"
        if i < len(rows) - 1:
            line += ','
        line += '\n'
        f.write(line)
    
    f.write(';\n')

print(f'✓ Exported vehicle_pricing_defaults: {sql_file}')

# Export fleet_number updates for vehicles
vehicles_sql = f'l:\\limo\\exports\\vehicles_fleet_number_update_{timestamp}.sql'

with open(vehicles_sql, 'w') as f:
    f.write('-- Vehicles Fleet Number Update\n')
    f.write(f'-- Exported: {timestamp}\n')
    f.write('-- This updates fleet_number to match vehicle_number\n\n')
    
    cur.execute(
        'SELECT vehicle_id, vehicle_number, fleet_number '
        'FROM vehicles WHERE fleet_number != vehicle_number OR fleet_number IS NULL '
        'ORDER BY vehicle_id'
    )
    
    updates = cur.fetchall()
    for vehicle_id, vehicle_number, _ in updates:
        f.write(f"UPDATE vehicles SET fleet_number = '{vehicle_number}' WHERE vehicle_id = {vehicle_id};\n")
    
    f.write(f'\n-- Total updates: {len(updates)}\n')

print(f'✓ Exported fleet_number updates: {vehicles_sql}')

cur.close()
conn.close()

print(f'\nExport ready for Neon sync. Import in this order:')
print(f'1. {sql_file}')
print(f'2. {vehicles_sql}')
