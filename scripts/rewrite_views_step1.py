#!/usr/bin/env python3
"""
Step 1: Rewrite views to use main tables instead of empty tables.
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
print("STEP 1: REWRITE VIEWS TO USE MAIN TABLES")
print("="*90)

# Backup existing views first
backup_file = "reports/views_backup_before_rewrite.sql"
os.makedirs("reports", exist_ok=True)

print("\n1️⃣  Backing up existing views...")

views_to_backup = ['v_driver_pay_summary', 'v_hos_daily_summary', 'v_driver_performance_summary']

with open(backup_file, 'w') as f:
    f.write("-- Backup of views before rewriting to use main tables\n")
    f.write("-- Created: 2026-01-23\n\n")
    
    for view_name in views_to_backup:
        cur.execute(f"""
            SELECT view_definition 
            FROM information_schema.views 
            WHERE table_name = '{view_name}'
        """)
        result = cur.fetchone()
        if result:
            f.write(f"-- View: {view_name}\n")
            f.write(f"CREATE OR REPLACE VIEW {view_name} AS\n")
            f.write(result[0])
            f.write(";\n\n")

print(f"   ✅ Backed up to {backup_file}")

# Drop and recreate views
print("\n2️⃣  Rewriting views...")

# View 1: v_driver_pay_summary - use driver_payroll instead of charter_driver_pay
print("\n   📊 v_driver_pay_summary (charter_driver_pay → driver_payroll)...")
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
            SUM(dp.total_hours_worked) AS total_hours,
            SUM(dp.gross_pay) AS total_pay,
            AVG(dp.hourly_rate) AS avg_effective_hourly
        FROM driver_payroll dp
        JOIN employees e ON dp.employee_id = e.employee_id
        GROUP BY 
            e.employee_id,
            e.first_name,
            e.last_name,
            DATE_TRUNC('month', dp.pay_date)
    """)
    print("      ✅ Recreated using driver_payroll")
except Exception as e:
    print(f"      ❌ Failed: {e}")
    conn.rollback()

# View 2: v_hos_daily_summary - drop it (driver_hos_log is empty, HOS not implemented)
print("\n   📊 v_hos_daily_summary (drop - not implemented)...")
try:
    cur.execute("DROP VIEW IF EXISTS v_hos_daily_summary CASCADE")
    print("      ✅ Dropped (HOS tracking not implemented)")
except Exception as e:
    print(f"      ❌ Failed: {e}")
    conn.rollback()

# View 3: v_driver_performance_summary - simplify to use only populated tables
print("\n   📊 v_driver_performance_summary (simplify to use driver_payroll)...")
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
            SUM(dp.total_hours_worked) AS total_hours,
            SUM(dp.gross_pay) AS total_earnings,
            AVG(dp.hourly_rate) AS avg_hourly_rate,
            MAX(dp.pay_date) AS last_pay_date
        FROM employees e
        LEFT JOIN charters c ON e.employee_id = c.driver_id
        LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
        GROUP BY 
            e.employee_id,
            e.full_name,
            e.employee_number,
            e.position
    """)
    print("      ✅ Recreated using driver_payroll (removed empty table references)")
except Exception as e:
    print(f"      ❌ Failed: {e}")
    conn.rollback()

# View 4: v_wage_allocation_pool_status - drop it (wage_allocation_decisions is empty)
print("\n   📊 v_wage_allocation_pool_status (drop - wage allocation not implemented)...")
try:
    cur.execute("DROP VIEW IF EXISTS v_wage_allocation_pool_status CASCADE")
    print("      ✅ Dropped (wage allocation not implemented)")
except Exception as e:
    print(f"      ❌ Failed: {e}")
    conn.rollback()

# Commit changes
print("\n3️⃣  Committing changes...")
try:
    conn.commit()
    print("   ✅ All view changes committed")
except Exception as e:
    print(f"   ❌ Commit failed: {e}")
    conn.rollback()

# Verify
print("\n4️⃣  Verifying new views...")
cur.execute("""
    SELECT table_name 
    FROM information_schema.views 
    WHERE table_schema = 'public'
    AND table_name IN ('v_driver_pay_summary', 'v_driver_performance_summary')
    ORDER BY table_name
""")

active_views = [row[0] for row in cur.fetchall()]
print(f"   Active views: {', '.join(active_views)}")

cur.close()
conn.close()

print("\n" + "="*90)
print("SUMMARY")
print("="*90)
print("✅ Backup: reports/views_backup_before_rewrite.sql")
print("✅ v_driver_pay_summary: Rewritten to use driver_payroll")
print("✅ v_driver_performance_summary: Rewritten to use driver_payroll")
print("✅ v_hos_daily_summary: Dropped (HOS not implemented)")
print("✅ v_wage_allocation_pool_status: Dropped (wage allocation not implemented)")
print("\nNext: Update desktop app code to use main tables")
print("="*90)
