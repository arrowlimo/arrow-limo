#!/usr/bin/env python
"""Find recent charters with routing data for testing"""
import sys, os
sys.path.insert(0, 'l:\\limo\\modern_backend')
os.chdir('l:\\limo')

import psycopg2
from config.database import DATABASE_CONFIG_LOCAL

# Find a recent charter with routing data
conn = psycopg2.connect(**DATABASE_CONFIG_LOCAL)
cur = conn.cursor()
cur.execute("""
SELECT charter_id, reserve_number, charter_date, driver_name, passenger_count, 
       (SELECT count(*) FROM routing WHERE charter_id = charters.charter_id) as route_count
FROM charters
WHERE charter_date >= CURRENT_DATE - INTERVAL '10 days'
  AND EXISTS (SELECT 1 FROM routing WHERE charter_id = charters.charter_id)
  AND passenger_count IS NOT NULL
ORDER BY charter_date DESC
LIMIT 3;
""")
rows = cur.fetchall()
conn.close()

print(f'Found {len(rows)} recent charters with routing:\n')
for cid, res, date, driver, pax, rcount in rows:
    print(f'  Charter: {cid:<6} Reserve: {res:<6} Date: {date}  Driver: {driver:<15} Pax: {pax}  Routes: {rcount}')
