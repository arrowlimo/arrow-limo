import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()

# Employees/drivers lookup
cur.execute("""
    SELECT e.employee_id, e.first_name, e.last_name, d.driver_id, d.first_name as d_first, d.last_name as d_last
    FROM employees e
    LEFT JOIN drivers d ON d.employee_id=e.employee_id
    WHERE e.employee_id IN (9,49,3,62,10,61,63,65,125,124,43,60,67,55,68,64,46,58)
    ORDER BY e.employee_id
""")
print("--- Employee/Driver mapping ---")
for r in cur.fetchall():
    print(r)

# Check how charter_payments links to charters (charter_id is varchar in payments)
cur.execute("""
    SELECT cp.charter_id, cp.client_name, cp.charter_date, cp.amount, cp.payment_method, cp.payment_key
    FROM charter_payments cp
    WHERE cp.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    LIMIT 5
""")
print("\n--- Charter payments sample ---")
for r in cur.fetchall():
    print(r)

# Check charter_id link
cur.execute("""
    SELECT c.charter_id, c.reserve_number, c.charter_date
    FROM charters c
    WHERE c.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    LIMIT 3
""")
print("\n--- Charters sample ---")
for r in cur.fetchall():
    print(r)

# Vehicles used in 2012
cur.execute("""
    SELECT v.vehicle_id, v.vehicle_number, v.make, v.model, v.year, v.description
    FROM vehicles v
    WHERE v.vehicle_id IN (
        SELECT DISTINCT vehicle_id FROM charters WHERE charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    )
    ORDER BY v.vehicle_number
""")
print("\n--- Vehicles in 2012 ---")
for r in cur.fetchall():
    print(r)

conn.close()
