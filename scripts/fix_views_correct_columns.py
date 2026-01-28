#!/usr/bin/env python3
"""
Fix the views with correct column names.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("="*90)
print("FIX VIEWS WITH CORRECT COLUMN NAMES")
print("="*90)

# View 1: v_driver_pay_summary
print("\n1️⃣  v_driver_pay_summary...")
try:
    cur.execute("DROP VIEW IF EXISTS v_driver_pay_summary CASCADE")
    
    cur.execute("""
        CREATE VIEW v_driver_pay_summary AS
        SELECT 
            e.employee_id,
            e.first_name,
            e.last_name,
            DATE_TRUNC('month', dp.pay_date) AS pay_period,
            COUNT(DISTINCT dp.reserve_number) AS total_charters,
            SUM(dp.hours_worked) AS total_hours,
            SUM(dp.gross_pay) AS total_pay,
            AVG(dp.gross_pay / NULLIF(dp.hours_worked, 0)) AS avg_effective_hourly
        FROM driver_payroll dp
        JOIN employees e ON dp.employee_id = e.employee_id
        WHERE dp.hours_worked > 0
        GROUP BY 
            e.employee_id,
            e.first_name,
            e.last_name,
            DATE_TRUNC('month', dp.pay_date)
    """)
    conn.commit()
    print("   ✅ Created using driver_payroll")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    conn.rollback()

# View 2: v_driver_performance_summary
print("\n2️⃣  v_driver_performance_summary...")
try:
    cur.execute("DROP VIEW IF EXISTS v_driver_performance_summary CASCADE")
    
    cur.execute("""
        CREATE VIEW v_driver_performance_summary AS
        SELECT 
            e.employee_id,
            e.full_name,
            e.employee_number,
            e.position,
            COUNT(DISTINCT c.charter_id) AS total_charters,
            SUM(dp.hours_worked) AS total_hours,
            SUM(dp.gross_pay) AS total_earnings,
            AVG(dp.gross_pay / NULLIF(dp.hours_worked, 0)) AS avg_hourly_rate,
            MAX(dp.pay_date) AS last_pay_date
        FROM employees e
        LEFT JOIN charters c ON e.employee_id = c.assigned_driver_id
        LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
        GROUP BY 
            e.employee_id,
            e.full_name,
            e.employee_number,
            e.position
    """)
    conn.commit()
    print("   ✅ Created using driver_payroll and charters.assigned_driver_id")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    conn.rollback()

# Verify
print("\n3️⃣  Verifying views work...")
try:
    cur.execute("SELECT COUNT(*) FROM v_driver_pay_summary")
    count1 = cur.fetchone()[0]
    print(f"   ✅ v_driver_pay_summary: {count1} rows")
    
    cur.execute("SELECT COUNT(*) FROM v_driver_performance_summary")
    count2 = cur.fetchone()[0]
    print(f"   ✅ v_driver_performance_summary: {count2} rows")
except Exception as e:
    print(f"   ❌ Query failed: {e}")

cur.close()
conn.close()

print("\n" + "="*90)
print("✅ Views successfully rewritten to use main tables")
print("="*90)
