import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("DELETING 53 EMPLOYEES WITH QB IDs IN employee_number FIELD")
print("="*100 + "\n")

# Find the employees to delete
cur.execute("""
    SELECT employee_id, employee_number, full_name,
           (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charters
    FROM employees
    WHERE employee_number LIKE '8%-%' 
       OR employee_number LIKE '%-%-%'
       OR LENGTH(employee_number) > 15
    ORDER BY employee_id
""")

to_delete = cur.fetchall()

print(f"Found {len(to_delete)} employees to delete:\n")

# Track what we're cleaning up
total_charters = 0
total_payroll = 0
deleted_ids = []

for emp_id, emp_num, name, payroll, charters in to_delete:
    print(f"  ID {emp_id:4d} | {name:25s} | {emp_num:30s} | P:{payroll} C:{charters}")
    total_charters += charters
    total_payroll += payroll
    deleted_ids.append(emp_id)

print(f"\nTotal business data to clean:")
print(f"  Payroll records: {total_payroll}")
print(f"  Charter assignments: {total_charters}")

# Clean up FK references
if total_charters > 0:
    print(f"\n[1/3] Nulling {total_charters} charter assignments...")
    cur.execute("""
        UPDATE charters 
        SET assigned_driver_id = NULL 
        WHERE assigned_driver_id = ANY(%s)
    """, (deleted_ids,))
    print(f"  ✓ Updated {cur.rowcount} charters")

if total_payroll > 0:
    print(f"\n[2/3] Deleting {total_payroll} payroll records...")
    cur.execute("DELETE FROM driver_payroll WHERE employee_id = ANY(%s)", (deleted_ids,))
    print(f"  ✓ Deleted {cur.rowcount} payroll records")

# Delete other FK references
print(f"\n[3/3] Cleaning up other FK references...")

tables_to_clean = [
    'employee_expenses',
    'driver_documents', 
    'employee_work_classifications',
    'driver_employee_mapping',
    'employee_availability',
    'employee_certifications'
]

total_cleaned = 0
for table in tables_to_clean:
    try:
        cur.execute(f"DELETE FROM {table} WHERE employee_id = ANY(%s)", (deleted_ids,))
        if cur.rowcount > 0:
            print(f"  ✓ {table}: deleted {cur.rowcount} records")
            total_cleaned += cur.rowcount
    except Exception as e:
        # Table might not exist or have FK
        conn.rollback()
        # Continue without this table
        continue

# Delete the employees
print(f"\n[FINAL] Deleting {len(deleted_ids)} employee records...")
cur.execute("DELETE FROM employees WHERE employee_id = ANY(%s)", (deleted_ids,))
deleted_count = cur.rowcount

conn.commit()

# Get final count
cur.execute("SELECT COUNT(*) FROM employees")
final_count = cur.fetchone()[0]

print("\n" + "="*100)
print(f"✅ DELETION COMPLETE")
print(f"{'='*100}")
print(f"  Employees deleted: {deleted_count}")
print(f"  Charters updated: {total_charters}")
print(f"  Payroll deleted: {total_payroll}")
print(f"  Other FK records: {total_cleaned}")
print(f"  Final employee count: {final_count}")
print("="*100 + "\n")

conn.close()
