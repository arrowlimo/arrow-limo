import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM vehicles WHERE fleet_number IS NULL OR fleet_number = '' OR fleet_number != vehicle_number")
before = cur.fetchone()[0]

cur.execute("UPDATE vehicles SET fleet_number = vehicle_number WHERE fleet_number IS NULL OR fleet_number = '' OR fleet_number != vehicle_number")
updated = cur.rowcount
conn.commit()

cur.execute("SELECT COUNT(*) FROM vehicles WHERE fleet_number IS NULL OR fleet_number = '' OR fleet_number != vehicle_number")
after = cur.fetchone()[0]

print(f"Rows needing backfill before: {before}")
print(f"Rows updated: {updated}")
print(f"Rows still mismatched after: {after}")

cur.close()
conn.close()
