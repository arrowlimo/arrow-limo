#!/usr/bin/env python3
"""
Driver ID Relationship Repair Suggestions - Corrected Analysis
Based on actual table schemas and data relationships
"""

import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata', 
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("🔧 DRIVER ID RELATIONSHIP REPAIR STRATEGY")
print("=" * 50)

print("📊 CURRENT RELATIONSHIP STATUS:")
print("=" * 35)

# Charter-driver linkage analysis
cur.execute("""
    SELECT COUNT(*) as total_charters,
           COUNT(assigned_driver_id) as with_driver_id,
           COUNT(DISTINCT assigned_driver_id) as unique_driver_ids
    FROM charters 
""")
charter_stats = cur.fetchone()
total, with_id, unique = charter_stats
print(f"📋 CHARTERS:")
print(f"  Total charters: {total:,}")
print(f"  With assigned_driver_id: {with_id:,} ({with_id/total*100:.1f}%)")
print(f"  Unique driver IDs assigned: {unique}")

# Payroll linkage analysis  
cur.execute("""
    SELECT COUNT(*) as total_payroll,
           COUNT(employee_id) as with_employee_id,
           COUNT(DISTINCT driver_id) as unique_driver_ids,
           COUNT(DISTINCT CAST(driver_id AS TEXT)) as unique_driver_strings
    FROM driver_payroll
""")
payroll_stats = cur.fetchone()
total_pay, with_emp_id, unique_drv, unique_str = payroll_stats
print(f"\n💰 PAYROLL:")
print(f"  Total payroll records: {total_pay:,}")
print(f"  With employee_id: {with_emp_id:,} ({with_emp_id/total_pay*100:.1f}%)")
print(f"  Unique driver_ids: {unique_drv}")

# Employee table analysis
cur.execute("""
    SELECT COUNT(*) as total_employees,
           COUNT(DISTINCT employee_number) as unique_emp_numbers,
           COUNT(full_name) as with_names,
           COUNT(CASE WHEN is_chauffeur = true THEN 1 END) as chauffeurs
    FROM employees
""")
emp_stats = cur.fetchone()
total_emp, unique_nums, with_names, chauffeurs = emp_stats
print(f"\n👥 EMPLOYEES:")
print(f"  Total employees: {total_emp}")
print(f"  Unique employee numbers: {unique_nums}")
print(f"  With names: {with_names}")
print(f"  Marked as chauffeurs: {chauffeurs}")

# Check driver_id patterns in payroll
print(f"\n🔍 DRIVER_ID PATTERNS IN PAYROLL:")
print("=" * 40)

cur.execute("""
    SELECT driver_id, COUNT(*) as records, 
           MIN(pay_date) as first_pay, MAX(pay_date) as last_pay,
           SUM(gross_pay) as total_pay
    FROM driver_payroll 
    WHERE driver_id IS NOT NULL
    GROUP BY driver_id
    ORDER BY COUNT(*) DESC
    LIMIT 15
""")
driver_patterns = cur.fetchall()

print("Top drivers by payroll frequency:")
for driver_id, records, first, last, total_pay in driver_patterns:
    total_pay = total_pay or 0
    print(f"  {driver_id}: {records:>4} records, ${total_pay:>8,.0f} ({first} to {last})")

# Check for potential employee_number matches
print(f"\n🔗 POTENTIAL LINKAGE OPPORTUNITIES:")
print("=" * 40)

cur.execute("""
    SELECT dp.driver_id, e.employee_id, e.full_name, e.employee_number,
           COUNT(dp.id) as payroll_records
    FROM driver_payroll dp
    JOIN employees e ON CAST(dp.driver_id AS TEXT) = CAST(e.employee_number AS TEXT)
    GROUP BY dp.driver_id, e.employee_id, e.full_name, e.employee_number
    ORDER BY COUNT(dp.id) DESC
    LIMIT 10
""")
potential_matches = cur.fetchall()

if potential_matches:
    print("Driver ID → Employee Number matches:")
    for driver_id, emp_id, name, emp_num, records in potential_matches:
        print(f"  {driver_id} → {name} (emp_id:{emp_id}, records:{records})")
else:
    print("No direct driver_id → employee_number matches found")

# Check charter-payroll reserve_number linkage
print(f"\n🎯 CHARTER-PAYROLL LINKAGE VIA RESERVE_NUMBER:")
print("=" * 50)

cur.execute("""
    SELECT COUNT(DISTINCT c.charter_id) as linked_charters,
           COUNT(DISTINCT dp.id) as linked_payroll,
           COUNT(*) as total_links
    FROM charters c
    JOIN driver_payroll dp ON CAST(c.reserve_number AS TEXT) = CAST(dp.reserve_number AS TEXT)
    WHERE c.charter_date >= '2020-01-01'  -- Recent data
""")
linkage_stats = cur.fetchone()

if linkage_stats and linkage_stats[0]:
    linked_charters, linked_payroll, total_links = linkage_stats
    print(f"Recent charters with payroll links: {linked_charters:,}")
    print(f"Payroll records linked to charters: {linked_payroll:,}")
    print(f"Total linkage relationships: {total_links:,}")
else:
    print("No reserve_number linkages found in recent data")

cur.close()
conn.close()

print(f"\n🛠️ COMPREHENSIVE REPAIR STRATEGY:")
print("=" * 40)

repair_steps = [
    "🎯 PHASE 1: ESTABLISH BASIC LINKAGES",
    "   1. Create driver_id → employee_id mapping table",
    "   2. Use employee_number field to match driver_payroll.driver_id", 
    "   3. Populate driver_payroll.employee_id from successful matches",
    "",
    "🔄 PHASE 2: CHARTER-DRIVER ASSIGNMENT",
    "   4. Use reserve_number to link charters → driver_payroll → employees",
    "   5. Populate charters.assigned_driver_id from payroll employee_id",
    "   6. Handle multiple drivers per charter (split shifts)",
    "",
    "🧹 PHASE 3: DATA CLEANUP",
    "   7. Standardize driver_id formats (remove leading zeros, etc.)",
    "   8. Resolve duplicate/conflicting assignments",
    "   9. Add NOT NULL constraints after repair",
    "",
    "⚡ PHASE 4: VALIDATION & TESTING", 
    "   10. Verify charter dates align with payroll dates",
    "   11. Check for impossible assignments (driver availability)",
    "   12. Generate driver performance/utilization reports",
    "",
    "🔮 PHASE 5: FUTURE IMPROVEMENTS",
    "   13. Implement dispatch system with proper ID validation",
    "   14. Add real-time driver assignment tracking", 
    "   15. Create driver scheduling conflict detection"
]

for step in repair_steps:
    print(step)

print(f"\n[OK] IMMEDIATE ACTION ITEMS:")
print("=" * 25)
print("1. Run: CREATE TABLE driver_employee_mapping (driver_id TEXT, employee_id INT)")
print("2. Populate mapping using employee_number matches")
print("3. Update driver_payroll.employee_id from mapping")
print("4. Update charters.assigned_driver_id via reserve_number linkage")
print("5. Add foreign key constraints to prevent future breaks")