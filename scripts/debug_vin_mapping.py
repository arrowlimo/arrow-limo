#!/usr/bin/env python3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=os.getenv('DB_PORT'),
    database=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
)
cur = conn.cursor()

sql = """
WITH e AS (
  SELECT id, entity, vin,
         regexp_replace(upper(coalesce(vin,'')), '[^A-Z0-9]', '', 'g') AS nvin,
         length(regexp_replace(upper(coalesce(vin,'')), '[^A-Z0-9]', '', 'g')) AS nlen
  FROM email_financial_events
  WHERE entity IN ('Heffner','CMB Insurance')
),
vv AS (
  SELECT vehicle_id, make, model, license_plate, vin_number,
         regexp_replace(upper(coalesce(vin_number,'')), '[^A-Z0-9]', '', 'g') AS nvin
  FROM vehicles
),
m AS (
  SELECT e.*, v.vehicle_id AS matched_vehicle_exact
  FROM e LEFT JOIN vv v ON v.nvin = e.nvin AND e.nlen = 17
),
m8 AS (
  SELECT e.*, v.vehicle_id AS matched_vehicle_last8
  FROM e LEFT JOIN vv v ON right(v.nvin, 8) = e.nvin AND e.nlen = 8
)
SELECT
  (SELECT COUNT(*) FROM e) AS total_events,
  (SELECT COUNT(*) FROM e WHERE vin IS NOT NULL AND vin <> '') AS with_vin,
  (SELECT COUNT(*) FROM e WHERE nlen = 17) AS len17,
  (SELECT COUNT(*) FROM e WHERE nlen = 8) AS len8,
  (SELECT COUNT(*) FROM m WHERE matched_vehicle_exact IS NOT NULL) AS matched_exact,
  (SELECT COUNT(*) FROM m8 WHERE matched_vehicle_last8 IS NOT NULL) AS matched_last8
;
"""
cur.execute(sql)
row = cur.fetchone()
print({
    'total_events': row[0],
    'with_vin': row[1],
    'len17': row[2],
    'len8': row[3],
    'matched_exact': row[4],
    'matched_last8': row[5],
})

# Show a few sample vins
cur.execute("""
SELECT vin, regexp_replace(upper(coalesce(vin,'')), '[^A-Z0-9]', '', 'g') AS nvin,
       length(regexp_replace(upper(coalesce(vin,'')), '[^A-Z0-9]', '', 'g')) AS nlen,
       COUNT(*)
FROM email_financial_events
WHERE entity IN ('Heffner','CMB Insurance')
GROUP BY 1,2,3
ORDER BY nlen DESC NULLS LAST, count DESC
LIMIT 20;
""")
print('Samples:')
for r in cur.fetchall():
    print(r)

cur.close(); conn.close()
print('Done')
