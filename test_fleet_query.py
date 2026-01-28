import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("Testing FleetManagementWidget Query")
print("="*80)

# Exact query from dashboard_classes.py line 82
query = """
SELECT v.vehicle_id, v.vehicle_number, v.make, v.model, v.year,
    COALESCE(SUM(CASE WHEN r.description ILIKE '%fuel%' THEN r.gross_amount ELSE 0 END),0) fuel_cost,
    COALESCE(SUM(CASE WHEN r.description ILIKE '%maint%' OR r.description ILIKE '%repair%' THEN r.gross_amount ELSE 0 END),0) maint_cost
FROM vehicles v
LEFT JOIN receipts r ON v.vehicle_id = r.vehicle_id
GROUP BY v.vehicle_id, v.vehicle_number, v.make, v.model, v.year
ORDER BY v.vehicle_number
"""

try:
    cur.execute(query)
    rows = cur.fetchall()
    print(f"✅ Query executed successfully")
    print(f"Rows returned: {len(rows)}")
    print("\nFirst 10 results:")
    print("-"*80)
    for i, (vid, vnum, make, model, year, fuel, maint) in enumerate(rows[:10], 1):
        total = float(fuel or 0) + float(maint or 0)
        print(f"{i:2}. {vnum:15} | {make:15} {model:20} | {year} | Fuel: ${fuel:>8.2f} | Maint: ${maint:>8.2f} | Total: ${total:>10.2f}")
except Exception as e:
    print(f"❌ Query failed: {e}")
    import traceback
    traceback.print_exc()

cur.close()
conn.close()
