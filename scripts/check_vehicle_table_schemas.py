import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

tables = ['vehicle_documents', 'vehicle_insurance', 'maintenance_records', 'vehicle_fuel_log']

for table in tables:
    cur.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name=%s
        ORDER BY ordinal_position
    """, (table,))
    
    print(f"\n{table}:")
    print("="*60)
    for row in cur.fetchall():
        print(f"  {row[0]:30} {row[1]}")

cur.close()
conn.close()
