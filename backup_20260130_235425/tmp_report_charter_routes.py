#!/usr/bin/env python3
import os
import psycopg2

pg = psycopg2.connect(
    host=os.getenv("DB_HOST", "localhost"),
    dbname=os.getenv("DB_NAME", "almsdata"),
    user=os.getenv("DB_USER", "postgres"),
    password=os.getenv("DB_PASSWORD", "ArrowLimousine"),
)
cur = pg.cursor()
cur.execute("SELECT count(*) FROM charter_routes")
total = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM charter_routes WHERE pickup_location IS NOT NULL")
pu_loc = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM charter_routes WHERE dropoff_location IS NOT NULL")
do_loc = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM charter_routes WHERE pickup_time IS NOT NULL")
pu_time = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM charter_routes WHERE dropoff_time IS NOT NULL")
do_time = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM charter_routes WHERE route_notes IS NOT NULL")
notes = cur.fetchone()[0]
print(f"total={total}")
print(f"pickup_location={pu_loc}")
print(f"dropoff_location={do_loc}")
print(f"pickup_time={pu_time}")
print(f"dropoff_time={do_time}")
print(f"route_notes={notes}")

cur.execute(
    """
    SELECT c.reserve_number, cr.pickup_location, cr.dropoff_location, cr.pickup_time, cr.dropoff_time
    FROM charter_routes cr
    JOIN charters c ON c.charter_id = cr.charter_id
    WHERE cr.dropoff_location IS NOT NULL
    ORDER BY cr.charter_id
    LIMIT 5
    """
)
print("\nSample with dropoff_location:")
for row in cur.fetchall():
    print(row)

cur.close()
pg.close()
