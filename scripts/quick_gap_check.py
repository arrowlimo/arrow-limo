import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("\n" + "="*100)
print("QUICK GAP CHECK - 2024")
print("="*100)

# Simple direct check
cur.execute("""
    SELECT 
        e.name,
        COUNT(DISTINCT epm.pay_period_id) as periods_with_data,
        SUM(COALESCE(epm.gross_pay, 0)) as calculated_gross,
        t4.t4_employment_income as t4_income,
        ROUND(t4.t4_employment_income - SUM(COALESCE(epm.gross_pay, 0))) as gap
    FROM employees e
    JOIN employee_t4_summary t4 ON e.employee_id = t4.employee_id AND t4.fiscal_year = 2024
    LEFT JOIN employee_pay_master epm ON epm.employee_id = e.employee_id
    GROUP BY e.name, t4.t4_employment_income
    ORDER BY gap DESC, e.name
    LIMIT 20
""")

print(f"\n{'Employee':<25} | {'Periods w/ Data'} | {'Calculated Gross':<16} | {'T4 Income':<16} | {'Gap'}")
print("-" * 100)

for name, periods, calc_gross, t4_income, gap in cur.fetchall():
    periods = periods or 0
    calc_gross = calc_gross or 0
    gap = gap or 0
    print(f"{name:<25} | {periods:>14} | ${calc_gross:>14,.0f} | ${t4_income:>14,.0f} | ${gap:>12,.0f}")

cur.close()
conn.close()
