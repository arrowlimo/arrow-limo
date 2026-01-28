import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM vehicle_pricing_defaults')
count = cur.fetchone()[0]
print(f'Total vehicle types in pricing table: {count}')
print()

cur.execute(
    'SELECT vehicle_type, nrr, hourly_rate, daily_rate, standby_rate, '
    'airport_pickup_calgary, airport_pickup_edmonton, hourly_package, fee_1, fee_2, fee_3 '
    'FROM vehicle_pricing_defaults ORDER BY vehicle_type'
)

print('Vehicle Pricing Summary:')
print()

for row in cur.fetchall():
    vtype, nrr, hrate, drate, srate, calgary, edmonton, pkg, f1, f2, f3 = row
    pkg_str = str(pkg) if pkg else 'None'
    print(f'{vtype:40s} | NRR: {nrr:6.2f} | Base: {hrate:6.2f} | Daily: {drate:6.2f} | Standby: {srate:6.2f}')
    print(f'  Airport: YYC={calgary:6.2f} YEG={edmonton:6.2f} | Package: {pkg_str:6s} | Fees: {f1:.2f}/{f2:.2f}/{f3:.2f}')
    print()

cur.close()
conn.close()
