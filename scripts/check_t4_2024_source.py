import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("T4 2024 data verification...")
cur.execute("""
    SELECT 
        employee_id,
        fiscal_year,
        t4_employment_income,
        t4_federal_tax,
        t4_provincial_tax,
        t4_cpp_contributions,
        t4_ei_contributions,
        source,
        confidence_level
    FROM employee_t4_summary
    WHERE fiscal_year = 2024
    ORDER BY t4_employment_income DESC
""")

print(f"{'Employee':<6} | {'T4 Income':<15} | {'Fed Tax':<10} | {'Prov Tax':<10} | {'CPP':<10} | {'EI':<10} | {'Source':<20} | {'Conf%'}")
print("-" * 105)

total_income = 0
for emp_id, year, income, fed, prov, cpp, ei, source, confidence in cur.fetchall():
    total_income += income or 0
    print(f"{emp_id:<6} | ${income or 0:>13,.0f} | ${fed or 0:>8,.0f} | ${prov or 0:>8,.0f} | ${cpp or 0:>8,.0f} | ${ei or 0:>8,.0f} | {source:<20} | {confidence or 0:>3.0f}%")

print("-" * 105)
print(f"{'TOTAL':<6} | ${total_income:>13,.0f}")

print(f"\n\nNOTE: All records have source='reconstructed' - these are CALCULATED from employee_pay_calc, not from actual T4 forms!")

cur.close()
conn.close()
