import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("Checking T4 2024 data...")
cur.execute("SELECT COUNT(*) FROM employee_t4_summary WHERE fiscal_year = 2024")
count = cur.fetchone()[0]
print(f"T4 records for 2024: {count}")

print("\nChecking employee_pay_master 2024 data...")
cur.execute("""
    SELECT COUNT(DISTINCT employee_id) 
    FROM employee_pay_master epm
    JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
    WHERE pp.fiscal_year = 2024 AND epm.gross_pay > 0
""")
count = cur.fetchone()[0]
print(f"Employees with pay data in 2024: {count}")

print("\nDirect gap check (simplified)...")
cur.execute("""
    SELECT 
        t4.employee_id,
        (SELECT e.name FROM employees e WHERE e.employee_id = t4.employee_id) as name,
        t4.fiscal_year,
        t4.t4_employment_income,
        (SELECT SUM(epm.gross_pay) FROM employee_pay_master epm 
         JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
         WHERE epm.employee_id = t4.employee_id AND pp.fiscal_year = 2024) as calculated_total
    FROM employee_t4_summary t4
    WHERE t4.fiscal_year = 2024
    LIMIT 5
""")

for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
