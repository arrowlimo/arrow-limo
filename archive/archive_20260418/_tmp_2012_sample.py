import psycopg2
conn = psycopg2.connect(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")
cur = conn.cursor()

# Count 2012 charters
cur.execute("SELECT COUNT(*) FROM charters WHERE charter_date BETWEEN '2012-01-01' AND '2012-12-31'")
print("2012 charter count:", cur.fetchone()[0])

# Sample charter row
cur.execute("""SELECT reserve_number, charter_date, client_id, client_display_name, employee_id, driver, 
               vehicle_id, vehicle, actual_hours, approved_hours, quoted_hours
               FROM charters WHERE charter_date BETWEEN '2012-01-01' AND '2012-12-31'
               LIMIT 3""")
for r in cur.fetchall():
    print("Charter:", r)

# Distinct charge descriptions in 2012
cur.execute("""
    SELECT cc.description, cc.charge_type, COUNT(*), SUM(cc.amount)
    FROM charter_charges cc
    JOIN charters c ON c.charter_id=cc.charter_id
    WHERE c.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    GROUP BY cc.description, cc.charge_type
    ORDER BY COUNT(*) DESC
    LIMIT 30
""")
print("\n--- Charge descriptions 2012 ---")
for r in cur.fetchall():
    print(r)

# Payments for 2012
cur.execute("""
    SELECT cp.payment_method, cp.source, COUNT(*), SUM(cp.amount)
    FROM charter_payments cp
    WHERE cp.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    GROUP BY cp.payment_method, cp.source ORDER BY COUNT(*) DESC LIMIT 20
""")
print("\n--- 2012 payment methods ---")
for r in cur.fetchall():
    print(r)

# Employees/drivers in 2012 charters
cur.execute("""
    SELECT c.employee_id, c.driver, COUNT(*) as cnt
    FROM charters c 
    WHERE c.charter_date BETWEEN '2012-01-01' AND '2012-12-31'
    GROUP BY c.employee_id, c.driver ORDER BY cnt DESC LIMIT 20
""")
print("\n--- Drivers in 2012 ---")
for r in cur.fetchall():
    print(r)

conn.close()
