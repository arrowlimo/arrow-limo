import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(f"host={DB_HOST} dbname={DB_NAME} user={DB_USER} password={DB_PASSWORD}")
cur = conn.cursor()

print("Charter data analysis...")
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM charter_date) as year,
        COUNT(*) as charter_count,
        COUNT(DISTINCT assigned_driver_id) as drivers,
        SUM(driver_hours_worked) as total_hours,
        AVG(driver_hours_worked) as avg_hours,
        MIN(charter_date) as first_date,
        MAX(charter_date) as last_date
    FROM charters
    WHERE driver_hours_worked > 0
    GROUP BY EXTRACT(YEAR FROM charter_date)
    ORDER BY year DESC
    LIMIT 10
""")

print(f"{'Year':<6} | {'Charters':<10} | {'Drivers':<8} | {'Total Hours':<15} | {'Avg Hours':<12} | {'Date Range'}")
print("-" * 85)
for year, count, drivers, hours, avg_hours, first_date, last_date in cur.fetchall():
    if year is not None:
        print(f"{int(year):<6} | {count:<10} | {drivers:<8} | {hours or 0:>13,.0f} | {avg_hours or 0:>10.1f} | {first_date} to {last_date}")

print("\n\nCharter data by employee (2024):")
cur.execute("""
    SELECT 
        c.assigned_driver_id,
        e.name,
        COUNT(*) as charter_count,
        SUM(c.driver_hours_worked) as total_hours
    FROM charters c
    LEFT JOIN employees e ON c.assigned_driver_id = e.employee_id
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2024
      AND c.driver_hours_worked > 0
    GROUP BY c.assigned_driver_id, e.name
    ORDER BY total_hours DESC
    LIMIT 20
""")

print(f"{'Employee':<25} | {'Charters':<10} | {'Total Hours'}")
print("-" * 50)
for emp_id, name, charter_count, total_hours in cur.fetchall():
    print(f"{name or f'ID:{emp_id}':<25} | {charter_count:<10} | {total_hours or 0:>12,.0f}")

cur.close()
conn.close()
