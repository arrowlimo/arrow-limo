#!/usr/bin/env python
"""TIER 2A: Create charter_hours_allocation view.
Sum charter hours by employee/pay_period from dispatcher data.
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD",os.environ.get("DB_PASSWORD"))

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("TIER 2A: CREATE CHARTER_HOURS_ALLOCATION VIEW")
print("="*100)
print()

# Drop if exists
cur.execute("DROP VIEW IF EXISTS charter_hours_allocation CASCADE")
print("✅ Dropped existing view")

# Create view
cur.execute("""
    CREATE VIEW charter_hours_allocation AS
    SELECT 
        c.assigned_driver_id as employee_id,
        pp.pay_period_id,
        pp.fiscal_year,
        pp.period_number,
        pp.period_start_date,
        pp.period_end_date,
        pp.pay_date,
        COUNT(*) as trip_count,
        SUM(c.driver_hours_worked) as total_hours,
        AVG(c.driver_hours_worked) as avg_hours_per_trip,
        MIN(c.charter_date) as first_charter_date,
        MAX(c.charter_date) as last_charter_date,
        SUM(c.driver_base_pay) as base_pay_from_charters,
        SUM(c.driver_gratuity_amount) as gratuity_from_charters,
        COUNT(DISTINCT c.charter_date) as distinct_days_worked,
        e.hourly_rate,
        e.first_name || ' ' || e.last_name as employee_name
    FROM charters c
    JOIN employees e ON c.assigned_driver_id = e.employee_id
    JOIN pay_periods pp ON c.charter_date >= pp.period_start_date 
                        AND c.charter_date <= pp.period_end_date
                        AND EXTRACT(YEAR FROM c.charter_date) = pp.fiscal_year
    WHERE c.assigned_driver_id IS NOT NULL
      AND c.driver_hours_worked IS NOT NULL
    GROUP BY 
        c.assigned_driver_id,
        pp.pay_period_id,
        pp.fiscal_year,
        pp.period_number,
        pp.period_start_date,
        pp.period_end_date,
        pp.pay_date,
        e.hourly_rate,
        e.employee_id,
        e.first_name,
        e.last_name
""")
print("✅ Created charter_hours_allocation view")

# Show sample data
print("\nSample: 2024-Q1 Hours by Employee")
print("-" * 100)
cur.execute("""
    SELECT 
        employee_name,
        period_number,
        trip_count,
        total_hours,
        base_pay_from_charters,
        gratuity_from_charters
    FROM charter_hours_allocation
    WHERE fiscal_year = 2024 AND period_number <= 3
    ORDER BY period_number, employee_name
    LIMIT 20
""")
print("Employee | Period | Trips | Hours | Base Pay | Gratuity")
print("-" * 100)
for emp, period, trips, hours, base, grat in cur.fetchall():
    hours = hours or 0
    base = base or 0
    grat = grat or 0
    print(f"{emp:<30} | {period:>2} | {trips:>5} | {hours:>7.1f} | ${base:>10,.2f} | ${grat:>8,.2f}")

# Summary statistics
print("\nAllocation Coverage 2024:")
print("-" * 100)
cur.execute("""
    SELECT 
        COUNT(DISTINCT employee_id) as employees_with_hours,
        COUNT(DISTINCT pay_period_id) as pay_periods_covered,
        SUM(trip_count) as total_trips,
        SUM(total_hours) as total_hours_allocated,
        SUM(base_pay_from_charters) as total_base_pay,
        SUM(gratuity_from_charters) as total_gratuity
    FROM charter_hours_allocation
    WHERE fiscal_year = 2024
""")
emp_cnt, period_cnt, trips, hours, base, grat = cur.fetchone()
print(f"Employees with hours: {emp_cnt}")
print(f"Pay periods covered: {period_cnt}")
print(f"Total trips: {trips:,}")
print(f"Total hours: {hours:,.1f}")
print(f"Total base pay: ${base:,.2f}")
print(f"Total gratuity: ${grat:,.2f}")

# Check for periods with no data
print("\n2024 Periods with NO charter hours:")
print("-" * 100)
cur.execute("""
    SELECT period_number, period_start_date, period_end_date
    FROM pay_periods
    WHERE fiscal_year = 2024
      AND pay_period_id NOT IN (
          SELECT DISTINCT pay_period_id
          FROM charter_hours_allocation
          WHERE fiscal_year = 2024
      )
    ORDER BY period_number
""")
no_data_periods = cur.fetchall()
if no_data_periods:
    for period, start, end in no_data_periods:
        print(f"Period {period:>2}: {start} to {end}")
else:
    print("✅ All 2024 periods have charter data!")

conn.commit()
cur.close()
conn.close()

print("\n✅ TIER 2A COMPLETE - CHARTER_HOURS_ALLOCATION VIEW CREATED!")
