import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("Checking employee_pay_master population by year...")
cur.execute("""
    SELECT 
        pp.fiscal_year,
        COUNT(*) as record_count,
        COUNT(DISTINCT epm.employee_id) as employees,
        SUM(epm.gross_pay) as total_gross,
        AVG(epm.gross_pay) as avg_gross
    FROM employee_pay_master epm
    JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
    WHERE epm.gross_pay > 0
    GROUP BY pp.fiscal_year
    ORDER BY fiscal_year DESC
    LIMIT 10
""")

print(f"{'Year':<6} | {'Records':<8} | {'Employees':<10} | {'Total Gross':<18} | {'Avg Gross'}")
print("-" * 70)
for year, count, employees, total, avg in cur.fetchall():
    print(f"{year:<6} | {count:<8} | {employees:<10} | ${total or 0:>16,.0f} | ${avg or 0:>10,.0f}")

print("\n\nT4 2024 vs Populated Data:")
print("-" * 70)
cur.execute("""
    SELECT 
        (SELECT SUM(t4_employment_income) FROM employee_t4_summary WHERE fiscal_year = 2024) as t4_total,
        (SELECT SUM(epm.gross_pay) FROM employee_pay_master epm
         JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
         WHERE pp.fiscal_year = 2024 AND epm.gross_pay > 0) as epm_total,
        (SELECT COUNT(*) FROM employee_pay_master epm
         JOIN pay_periods pp ON epm.pay_period_id = pp.pay_period_id
         WHERE pp.fiscal_year = 2024) as total_2024_records
""")

t4_total, epm_total, record_count = cur.fetchone()
print(f"T4 2024 Total: ${t4_total or 0:,.0f}")
print(f"EPM 2024 Total: ${epm_total or 0:,.0f}")
print(f"EPM 2024 Records: {record_count}")
print(f"Gap: ${(t4_total or 0) - (epm_total or 0):,.0f}")
print(f"Coverage: {100.0 * (epm_total or 0) / (t4_total or 1):.1f}%")

cur.close()
conn.close()
