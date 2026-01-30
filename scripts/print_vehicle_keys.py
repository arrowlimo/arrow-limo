import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REDACTED***')
    )

conn = get_db_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT vehicle_id, unit_number, license_plate FROM vehicles ORDER BY vehicle_id LIMIT 200")
rows = cur.fetchall()
print(f"vehicles rows: {len(rows)} (first 200)")
for r in rows:
    print(r['vehicle_id'], r['unit_number'], r['license_plate'])
cur.close(); conn.close()
