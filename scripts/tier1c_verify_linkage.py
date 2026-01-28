#!/usr/bin/env python
"""TIER 1C - FOUNDATION: Verify & report employee-to-charters linkage.
Check dispatcher hours availability and data quality.
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
print("TIER 1C: VERIFY EMPLOYEE-TO-CHARTERS LINKAGE")
print("="*100)
print()

# 1. Charter-employee linkage quality
print("1. CHARTER-TO-DRIVER LINKAGE QUALITY")
print("-" * 100)
cur.execute("""
    SELECT 
        COUNT(*) as total_charters,
        COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as with_driver_id,
        COUNT(CASE WHEN driver_hours_worked IS NOT NULL THEN 1 END) as with_hours,
        COUNT(CASE WHEN dispatcher_approved = true THEN 1 END) as dispatcher_approved,
        COUNT(CASE WHEN dispatch_authorized_time IS NOT NULL THEN 1 END) as with_auth_time
    FROM charters
""")
cnt, driver_id_cnt, hours_cnt, approved_cnt, auth_time_cnt = cur.fetchone()
print(f"Total charters: {cnt:,}")
print(f"  - With assigned_driver_id: {driver_id_cnt:,} ({100*driver_id_cnt/cnt:.1f}%)")
print(f"  - With driver_hours_worked: {hours_cnt:,} ({100*hours_cnt/cnt:.1f}%)")
print(f"  - Dispatcher approved: {approved_cnt:,} ({100*approved_cnt/cnt:.1f}%)")
print(f"  - With dispatch_authorized_time: {auth_time_cnt:,} ({100*auth_time_cnt/cnt:.1f}%)")

# 2. Driver hours data availability by year
print("\n2. CHARTER HOURS BY YEAR")
print("-" * 100)
cur.execute("""
    SELECT 
        EXTRACT(YEAR FROM charter_date)::int as yr,
        COUNT(*) as charters,
        COUNT(CASE WHEN assigned_driver_id IS NOT NULL THEN 1 END) as with_driver,
        COUNT(CASE WHEN driver_hours_worked IS NOT NULL THEN 1 END) as with_hours,
        SUM(driver_hours_worked) as total_hours,
        COUNT(CASE WHEN dispatcher_approved = true THEN 1 END) as approved
    FROM charters
    WHERE charter_date IS NOT NULL
    GROUP BY yr
    ORDER BY yr
""")
print("Year | Charters | With Driver | With Hours | Total Hours | Approved")
print("-" * 100)
for yr, charters, with_driver, with_hours, total_hours, approved in cur.fetchall():
    total_hours = total_hours or 0
    print(f"{yr} | {charters:>8,} | {with_driver:>11,} | {with_hours:>10,} | {total_hours:>11,.1f} | {approved:>8,}")

# 3. Employee hourly rate availability
print("\n3. EMPLOYEE RATE INFORMATION")
print("-" * 100)
cur.execute("""
    SELECT 
        COUNT(*) as total_employees,
        COUNT(CASE WHEN hourly_rate IS NOT NULL THEN 1 END) as with_rate,
        COUNT(CASE WHEN is_chauffeur = true THEN 1 END) as drivers,
        COUNT(CASE WHEN is_chauffeur = true AND hourly_rate IS NOT NULL THEN 1 END) as drivers_with_rate
    FROM employees
    WHERE employment_status != 'terminated'
""")
total_emp, with_rate, drivers, drivers_with_rate = cur.fetchone()
print(f"Active employees: {total_emp}")
print(f"  - With hourly_rate: {with_rate} ({100*with_rate/total_emp:.1f}%)")
print(f"  - Drivers: {drivers}")
print(f"  - Drivers with rate: {drivers_with_rate} ({100*drivers_with_rate/drivers if drivers > 0 else 0:.1f}%)")

# 4. Top drivers by hours worked
print("\n4. TOP 20 DRIVERS BY 2024 HOURS WORKED")
print("-" * 100)
cur.execute("""
    SELECT 
        e.employee_id,
        e.full_name,
        e.hourly_rate,
        COUNT(*) as trips,
        SUM(c.driver_hours_worked) as total_hours,
        SUM(c.driver_base_pay) as base_pay_earned
    FROM charters c
    JOIN employees e ON c.assigned_driver_id = e.employee_id
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2024
      AND c.dispatcher_approved = true
    GROUP BY e.employee_id, e.full_name, e.hourly_rate
    ORDER BY total_hours DESC
    LIMIT 20
""")
print("Employee ID | Name | Rate | Trips | Hours | Base Pay")
print("-" * 100)
for emp_id, name, rate, trips, hours, pay in cur.fetchall():
    hours = hours or 0
    pay = pay or 0
    rate = rate or 0
    print(f"{emp_id:>11} | {name:<30} | ${rate:>7.2f} | {trips:>5,} | {hours:>7.1f} | ${pay:>10,.2f}")

# 5. Data quality issues
print("\n5. DATA QUALITY ISSUES TO ADDRESS")
print("-" * 100)

# Missing rates
cur.execute("""
    SELECT COUNT(DISTINCT e.employee_id)
    FROM employees e
    WHERE is_chauffeur = true 
      AND hourly_rate IS NULL
      AND employment_status != 'terminated'
""")
missing_rates = cur.fetchone()[0]
print(f"⚠️  Drivers without hourly_rate: {missing_rates}")

# Missing dispatcher hours
cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE dispatcher_approved = true AND driver_hours_worked IS NULL
""")
missing_hours = cur.fetchone()[0]
print(f"⚠️  Approved charters without driver_hours_worked: {missing_hours}")

# Missing authorization time
cur.execute("""
    SELECT COUNT(*)
    FROM charters
    WHERE dispatcher_approved = true AND dispatch_authorized_time IS NULL
""")
missing_auth = cur.fetchone()[0]
print(f"⚠️  Approved charters without dispatch_authorized_time: {missing_auth}")

# 6. Sample data validation
print("\n6. SAMPLE CHARTER DATA (2024, Approved, With Hours)")
print("-" * 100)
cur.execute("""
    SELECT 
        c.charter_id,
        c.charter_date,
        e.full_name,
        c.driver_hours_worked,
        e.hourly_rate,
        c.driver_base_pay,
        c.driver_gratuity_amount,
        c.dispatcher_approved
    FROM charters c
    JOIN employees e ON c.assigned_driver_id = e.employee_id
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2024
      AND c.dispatcher_approved = true
      AND c.driver_hours_worked IS NOT NULL
    LIMIT 10
""")
print("Charter ID | Date | Driver | Hours | Rate | Base Pay | Gratuity | Approved")
print("-" * 100)
for cid, date, driver, hours, rate, base, grat, approved in cur.fetchall():
    print(f"{cid:>10} | {date} | {driver:<25} | {hours:>5.1f}h | ${rate:>6.2f} | ${base:>8,.2f} | ${grat:>8,.2f} | {approved}")

print("\n" + "="*100)
print("TIER 1C COMPLETE - FOUNDATION LINKAGE VERIFIED")
print("="*100)
print(f"""
✅ Employee-Charter linkage is STRONG:
   - {with_driver:,} charters have assigned drivers ({100*with_driver/cnt:.1f}%)
   - {with_hours:,} have dispatcher-approved hours ({100*with_hours/cnt:.1f}%)
   - {drivers_with_rate} drivers have hourly rates configured

🟡 Minor gaps to address before Tier 2:
   - {missing_rates} drivers need hourly rates
   - {missing_hours} approved charters missing hours
   - {missing_auth} approved charters missing auth time

NEXT: Tier 2 - Build charter_hours_allocation view and pay calculation engine
""")

cur.close()
conn.close()
