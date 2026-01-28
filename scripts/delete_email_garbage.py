import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*100)
print("DELETING 3 GARBAGE EMAIL/METADATA EMPLOYEES")
print("="*100 + "\n")

garbage_ids = [232, 246, 621]

# Show what we're deleting
cur.execute("""
    SELECT employee_id, full_name, first_name, last_name,
           (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charters
    FROM employees
    WHERE employee_id = ANY(%s)
""", (garbage_ids,))

rows = cur.fetchall()

print("Deleting these garbage records:\n")
for emp_id, full, first, last, pay, chrt in rows:
    print(f"  ID {emp_id:4d} | {full:40s} | P:{pay} C:{chrt}")

# Check FK references
cur.execute("SELECT COUNT(*) FROM charters WHERE assigned_driver_id = ANY(%s)", (garbage_ids,))
charter_count = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM driver_payroll WHERE employee_id = ANY(%s)", (garbage_ids,))
payroll_count = cur.fetchone()[0]

print(f"\nFK references:")
print(f"  Charters: {charter_count}")
print(f"  Payroll: {payroll_count}")

# Clean up FK references if needed
if charter_count > 0:
    print(f"\nNulling {charter_count} charter assignments...")
    cur.execute("UPDATE charters SET assigned_driver_id = NULL WHERE assigned_driver_id = ANY(%s)", (garbage_ids,))
    print(f"  ✓ Updated {cur.rowcount} charters")

if payroll_count > 0:
    print(f"\nDeleting {payroll_count} payroll records...")
    cur.execute("DELETE FROM driver_payroll WHERE employee_id = ANY(%s)", (garbage_ids,))
    print(f"  ✓ Deleted {cur.rowcount} payroll records")

# Delete the employees
print(f"\nDeleting {len(garbage_ids)} garbage employee records...")
cur.execute("DELETE FROM employees WHERE employee_id = ANY(%s)", (garbage_ids,))
deleted_count = cur.rowcount

conn.commit()

# Get final count
cur.execute("SELECT COUNT(*) FROM employees")
final_count = cur.fetchone()[0]

print("\n" + "="*100)
print(f"✅ DELETION COMPLETE")
print(f"{'='*100}")
print(f"  Employees deleted: {deleted_count}")
print(f"  Final employee count: {final_count}")
print("="*100 + "\n")

conn.close()
