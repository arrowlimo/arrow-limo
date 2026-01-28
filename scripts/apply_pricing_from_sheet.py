import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
)
cur = conn.cursor()

rows = [
    ('Sedan (3-4 pax)', 75, 75, 50, 18, 18, None),
    ('Luxury Sedan (4 pax)', 75, 120, 50, 18, 18, None),
    ('Luxury SUV (3-4 pax)', 75, 110, 50, 25, 25, None),
    ('Sedan Stretch (6 Pax)', 300, 150, 50, 25, 25, 110),
    ('SUV Stretch (13 pax)', 500, 250, 50, 25, 25, 145),
    ('Party Bus/ washroom (20 pax)', 500, 300, 50, 50, 50, 250),
    ('Shuttle Bus (14 pax)', 500, 150, 50, 50, 50, None),
    ('Shuttle Bus (18 pax)', 500, 175, 50, 50, 50, None),
    ('Party Bus (20 pax)', 500, 275, 50, 50, 50, 250),
    ('Shuttle Bus (27 pax)', 600, 225, 50, 60, 60, None),
    ('Party Bus (27 pax)', 600, 300, 50, 60, 60, None),
]

# Fix legacy typo before updates
cur.execute(
    "UPDATE vehicle_pricing_defaults SET vehicle_type = %s WHERE vehicle_type = %s",
    ('Sedan Stretch (6 Pax)', 'Sedan Stretch (6 Pax')
)

update_sql = (
    "UPDATE vehicle_pricing_defaults "
    "SET nrr = %s, "
    "hourly_rate = %s, "
    "standby_rate = %s, "
    "airport_pickup_calgary = %s, "
    "airport_pickup_edmonton = %s, "
    "hourly_package = %s, "
    "updated_at = NOW() "
    "WHERE vehicle_type = %s"
)

print("Updating rows...")
for vt, nrr, base, standby, calg, edm, pkg in rows:
    cur.execute(update_sql, (nrr, base, standby, calg, edm, pkg, vt))
    print(f"{vt}: NRR={nrr}, base={base}, standby={standby}, calg={calg}, edm={edm}, package={pkg}")

conn.commit()
print("Committed\n")

cur.execute(
    "SELECT vehicle_type, nrr, hourly_rate, standby_rate, "
    "airport_pickup_calgary, airport_pickup_edmonton, hourly_package "
    "FROM vehicle_pricing_defaults ORDER BY vehicle_type"
)
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
