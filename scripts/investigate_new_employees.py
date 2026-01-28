#!/usr/bin/env python3
"""
Investigate why Paul D Richard and Jeannie show as "new" employees.
Check what's actually in employees table vs staging.
"""
import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("="*80)
print("INVESTIGATING 'NEW' EMPLOYEES")
print("="*80)

# Check Paul D Richard in staging
print("\n1. STAGING: Paul D Richard")
cur.execute("""
    SELECT employee_id, employee_name, sin, hire_date, street1, city
    FROM staging_employee_reference_data
    WHERE LOWER(employee_name) LIKE '%paul%richard%'
""")
for row in cur.fetchall():
    print(f"   ID: {row[0]} | Name: {row[1]} | SIN: {row[2]} | Hired: {row[3]}")
    print(f"   Address: {row[4]}, {row[5]}")

# Check Paul in main employees table
print("\n2. MAIN TABLE: Paul D Richard / Paul Richard")
cur.execute("""
    SELECT employee_id, full_name, t4_sin, hire_date, employee_number
    FROM employees
    WHERE LOWER(full_name) LIKE '%paul%' AND LOWER(full_name) LIKE '%richard%'
    ORDER BY full_name
""")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"   ID: {row[0]} | Name: {row[1]} | SIN: {row[2]} | Hired: {row[3]} | Emp#: {row[4]}")
else:
    print("   [FAIL] NO PAUL RICHARD FOUND IN MAIN TABLE!")

# Check Jeannie in staging
print("\n3. STAGING: Jeannie Shillington")
cur.execute("""
    SELECT employee_id, employee_name, sin, hire_date, street1, city
    FROM staging_employee_reference_data
    WHERE LOWER(employee_name) LIKE '%jeannie%'
""")
for row in cur.fetchall():
    print(f"   ID: {row[0]} | Name: {row[1]} | SIN: {row[2]} | Hired: {row[3]}")
    print(f"   Address: {row[4]}, {row[5]}")

# Check Jeannie in main employees table
print("\n4. MAIN TABLE: Jeannie Shillington")
cur.execute("""
    SELECT employee_id, full_name, t4_sin, hire_date, employee_number
    FROM employees
    WHERE LOWER(full_name) LIKE '%jeannie%'
    ORDER BY full_name
""")
rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"   ID: {row[0]} | Name: {row[1]} | SIN: {row[2]} | Hired: {row[3]} | Emp#: {row[4]}")
else:
    print("   [FAIL] NO JEANNIE FOUND IN MAIN TABLE!")

# Check all staging vs main by SIN match
print("\n5. SIN MATCHING ANALYSIS")
cur.execute("""
    SELECT 
        serd.employee_name as staging_name,
        serd.sin as staging_sin,
        e.full_name as main_name,
        e.t4_sin as main_sin,
        CASE 
            WHEN e.employee_id IS NULL THEN 'NEW'
            WHEN serd.sin = e.t4_sin THEN 'EXACT SIN MATCH'
            ELSE 'NAME MATCH ONLY'
        END as match_type
    FROM staging_employee_reference_data serd
    LEFT JOIN employees e ON serd.sin = e.t4_sin
    ORDER BY match_type, serd.employee_name
""")
print(f"\n{'Staging Name':<30} {'Match Type':<20} {'Main Name':<30}")
print("-"*80)
for row in cur.fetchall():
    main_name = row[2] if row[2] else "NOT FOUND"
    print(f"{row[0]:<30} {row[4]:<20} {main_name:<30}")

# Check for NULL t4_sin in employees table
print("\n6. EMPLOYEES WITH NULL t4_sin")
cur.execute("""
    SELECT COUNT(*), COUNT(CASE WHEN t4_sin IS NULL OR t4_sin = '' THEN 1 END) as null_sin
    FROM employees
""")
total, null_count = cur.fetchone()
print(f"   Total employees: {total:,}")
print(f"   Missing t4_sin: {null_count:,} ({null_count/total*100:.1f}%)")

# Show sample employees with name matching staging
print("\n7. EMPLOYEES WITH MATCHING NAMES (but different SIN)")
cur.execute("""
    SELECT 
        serd.employee_name,
        serd.sin as staging_sin,
        e.full_name,
        e.t4_sin as main_sin,
        e.hire_date
    FROM staging_employee_reference_data serd
    INNER JOIN employees e ON LOWER(TRIM(serd.employee_name)) = LOWER(TRIM(e.full_name))
    WHERE serd.sin != COALESCE(e.t4_sin, '')
    ORDER BY serd.employee_name
""")
rows = cur.fetchall()
if rows:
    print(f"\n   Found {len(rows)} employees matching by name but with different SINs:")
    for row in rows:
        print(f"   {row[0]}: Staging SIN={row[1]} vs Main SIN={row[3] or 'NULL'} | Hired: {row[4]}")
else:
    print("   No name matches with different SINs")

cur.close()
conn.close()
