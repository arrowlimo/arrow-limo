import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("Sample employee_pay_master records:")
cur.execute("""
    SELECT 
        epm.employee_id,
        epm.fiscal_year,
        epm.charter_hours_sum,
        epm.gross_pay,
        epm.federal_tax,
        epm.provincial_tax,
        epm.cpp_employee,
        epm.ei_employee,
        epm.net_pay
    FROM employee_pay_master epm
    LIMIT 5
""")

for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
