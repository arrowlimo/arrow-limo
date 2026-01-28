#!/usr/bin/env python3
"""Check for duplicate employee records."""
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
print("DUPLICATE EMPLOYEE ANALYSIS")
print("="*80)

# Check for duplicate names (case-insensitive)
print("\n1. EMPLOYEES WITH DUPLICATE NAMES:")
cur.execute("""
    SELECT 
        LOWER(TRIM(full_name)) as normalized_name,
        COUNT(*) as count,
        STRING_AGG(employee_id::TEXT || ': ' || full_name, ' | ' ORDER BY employee_id) as records
    FROM employees
    GROUP BY LOWER(TRIM(full_name))
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC, normalized_name
""")

duplicates = cur.fetchall()
print(f"\nFound {len(duplicates)} names with multiple records:\n")

for name, count, records in duplicates:
    print(f"{name} ({count} records):")
    print(f"  {records}")
    print()

# Check Logan Mosinsky specifically (we updated both with same SIN)
print("\n2. LOGAN MOSINSKY DETAIL:")
cur.execute("""
    SELECT employee_id, full_name, t4_sin, hire_date, employee_number
    FROM employees
    WHERE LOWER(full_name) LIKE '%logan%mosinsky%'
    ORDER BY employee_id
""")

for row in cur.fetchall():
    print(f"  ID {row[0]}: {row[1]} | SIN: {row[2]} | Hired: {row[3]} | Emp#: {row[4]}")

# Check Paul D Richard (owner - mentioned having 3 records)
print("\n3. PAUL D RICHARD (OWNER) DETAIL:")
cur.execute("""
    SELECT employee_id, full_name, t4_sin, hire_date, employee_number, salary
    FROM employees
    WHERE LOWER(full_name) LIKE '%paul%richard%'
    ORDER BY employee_id
""")

for row in cur.fetchall():
    salary = f"${row[5]:,.2f}" if row[5] else "N/A"
    print(f"  ID {row[0]}: {row[1]} | SIN: {row[2]} | Hired: {row[3]} | Emp#: {row[4]} | Salary: {salary}")

# Check Jeannie Shillington (mentioned having 4 records)
print("\n4. JEANNIE SHILLINGTON DETAIL:")
cur.execute("""
    SELECT employee_id, full_name, t4_sin, hire_date, employee_number
    FROM employees
    WHERE LOWER(full_name) LIKE '%jeannie%'
    ORDER BY employee_id
""")

for row in cur.fetchall():
    print(f"  ID {row[0]}: {row[1]} | SIN: {row[2]} | Hired: {row[3]} | Emp#: {row[4]}")

print("\n" + "="*80)
print("RECOMMENDATION:")
print("="*80)
print("\nDuplicates should be consolidated by:")
print("1. Keeping the record with the most complete data")
print("2. Updating any foreign key references (charters, payroll, etc.)")
print("3. Deleting duplicate records")
print("\nFor Logan Mosinsky: Both records now have same SIN - merge into one")
print("For Paul D Richard: Keep ID with complete SIN/hire date, delete others")
print("For Jeannie: Keep ID with complete SIN/hire date, delete others")

cur.close()
conn.close()
