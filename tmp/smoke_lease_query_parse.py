import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine',
)
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM vehicle_lease_profiles')
count_profiles = cur.fetchone()[0]
print('lease_profiles_count', count_profiles)

# Parse/execute query shape independent of data presence.
cur.execute(
    """
    SELECT
        v.vehicle_number, v.make, v.model, v.year, v.vin_number,
        lp.lease_status
    FROM vehicle_lease_profiles lp
    JOIN vehicles v ON v.vehicle_id = lp.vehicle_id
    LIMIT 0
    """
)
print('lease_query_parse_ok', True)

cur.close()
conn.close()
