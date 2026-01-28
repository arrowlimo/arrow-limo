import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("Checking employee_pay_master data...")
cur.execute("SELECT COUNT(*) FROM employee_pay_master")
count = cur.fetchone()[0]
print(f"Total rows in employee_pay_master: {count}")

print("\nSample data:")
cur.execute("SELECT employee_id, pay_period_id, gross_pay FROM employee_pay_master LIMIT 5")
for row in cur.fetchall():
    print(row)

print("\nChecking 2024 pay periods...")
cur.execute("SELECT COUNT(*) FROM pay_periods WHERE fiscal_year = 2024")
count = cur.fetchone()[0]
print(f"Pay periods in 2024: {count}")

print("\nChecking employee_t4_summary 2024...")
cur.execute("SELECT COUNT(*) FROM employee_t4_summary WHERE fiscal_year = 2024")
count = cur.fetchone()[0]
print(f"T4 records for 2024: {count}")

cur.close()
conn.close()
