"""
Check if charters.assigned_driver_id links to employees.employee_id
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("ANALYZING DRIVER ID RELATIONSHIPS")
print("=" * 80)

# Check if assigned_driver_id matches employee_id
cur.execute("""
    SELECT 
        COUNT(DISTINCT c.assigned_driver_id) as unique_driver_ids,
        COUNT(DISTINCT e.employee_id) as matching_employees
    FROM charters c
    LEFT JOIN employees e ON c.assigned_driver_id = e.employee_id
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
    AND c.assigned_driver_id IS NOT NULL
    AND c.assigned_driver_id != 0
""")

row = cur.fetchone()
print(f"\nUnique assigned_driver_id values in 2012 charters: {row[0]}")
print(f"Matching employees found: {row[1]}")

# Sample the mapping
cur.execute("""
    SELECT 
        c.assigned_driver_id,
        e.employee_id,
        e.full_name,
        COUNT(c.charter_id) as charter_count
    FROM charters c
    LEFT JOIN employees e ON c.assigned_driver_id = e.employee_id
    WHERE EXTRACT(YEAR FROM c.charter_date) = 2012
    AND c.assigned_driver_id IS NOT NULL
    AND c.assigned_driver_id != 0
    GROUP BY c.assigned_driver_id, e.employee_id, e.full_name
    ORDER BY charter_count DESC
    LIMIT 15
""")

print(f"\n{'Driver ID':<12} {'Emp ID':<10} {'Employee Name':<30} {'Charters':>10}")
print("-" * 80)

for row in cur.fetchall():
    driver_id, emp_id, name, count = row
    print(f"{driver_id:<12} {emp_id or 'NOT FOUND':<10} {name or 'NOT FOUND':<30} {count:>10}")

# Check if we should use assigned_driver_id directly as employee_id
print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

if row[0] == row[1]:
    print("[OK] assigned_driver_id MATCHES employee_id")
    print("   We can join charters.assigned_driver_id = employees.employee_id")
else:
    print("[WARN] assigned_driver_id does NOT directly match employee_id")
    print("   We must continue using reserve_number for joins")

cur.close()
conn.close()
