import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("Checking charter_hours_allocation data...")
cur.execute("SELECT COUNT(*) FROM charter_hours_allocation")
count = cur.fetchone()[0]
print(f"Total rows in charter_hours_allocation: {count}")

print("\n2024 charter_hours_allocation sample:")
cur.execute("""
    SELECT 
        employee_id,
        pay_period_id,
        total_hours,
        base_pay_from_charters,
        gratuity_from_charters
    FROM charter_hours_allocation
    WHERE pay_period_id IN (SELECT pay_period_id FROM pay_periods WHERE fiscal_year = 2024)
    LIMIT 10
""")

for row in cur.fetchall():
    print(row)

print("\n\n2024 charter_hours_allocation summary:")
cur.execute("""
    SELECT 
        COUNT(*) as record_count,
        COUNT(DISTINCT employee_id) as employees,
        COUNT(DISTINCT pay_period_id) as periods,
        SUM(total_hours) as total_hours,
        SUM(base_pay_from_charters) as total_base,
        SUM(gratuity_from_charters) as total_gratuity
    FROM charter_hours_allocation cha
    WHERE pay_period_id IN (SELECT pay_period_id FROM pay_periods WHERE fiscal_year = 2024)
""")

records, employees, periods, hours, base, gratuity = cur.fetchone()
print(f"Records: {records}")
print(f"Employees: {employees}")
print(f"Periods: {periods}")
print(f"Total hours: {hours or 0}")
print(f"Total base: ${base or 0:,.0f}")
print(f"Total gratuity: ${gratuity or 0:,.0f}")
print(f"Total gross: ${(base or 0) + (gratuity or 0):,.0f}")

cur.close()
conn.close()
