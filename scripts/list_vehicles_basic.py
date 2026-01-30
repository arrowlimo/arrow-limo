#!/usr/bin/env python3
import psycopg2

conn=psycopg2.connect(host='localhost',database='almsdata',user='postgres',password='***REDACTED***')
cur=conn.cursor()
cur.execute("""
    SELECT vehicle_id, vehicle_number, fleet_number, unit_number, make, model, license_plate
    FROM vehicles
    ORDER BY vehicle_id
""")
rows=cur.fetchall()
print(f"{'vehicle_id':<10} {'vehicle_number':<15} {'fleet_number':<12} {'unit_number':<12} {'make':<10} {'model':<15} {'license_plate':<12}")
for r in rows:
    print(f"{r[0]:<10} {str(r[1] or ''):<15} {str(r[2] or ''):<12} {str(r[3] or ''):<12} {str(r[4] or ''):<10} {str(r[5] or ''):<15} {str(r[6] or ''):<12}")
cur.close(); conn.close()
