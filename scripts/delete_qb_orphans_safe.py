import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("SAFELY DELETING 53 QB ORPHAN EMPLOYEES")
print("="*100 + "\n")

# Find the employees to delete
cur.execute("""
    SELECT employee_id, employee_number, full_name
    FROM employees
    WHERE employee_number LIKE '8%-%' 
       OR employee_number LIKE '%-%-%'
       OR LENGTH(employee_number) > 15
    ORDER BY employee_id
""")

to_delete = [(r[0], r[1], r[2]) for r in cur.fetchall()]
deleted_ids = [r[0] for r in to_delete]

print(f"Found {len(to_delete)} employees to delete\n")

# Check ALL FK references before deleting
print("[1/6] Checking charter references...")
cur.execute("SELECT COUNT(*) FROM charters WHERE assigned_driver_id = ANY(%s)", (deleted_ids,))
charter_count = cur.fetchone()[0]
print(f"  Found {charter_count} charter assignments")

print("[2/6] Checking payroll references...")
cur.execute("SELECT COUNT(*) FROM driver_payroll WHERE employee_id = ANY(%s)", (deleted_ids,))
payroll_count = cur.fetchone()[0]
print(f"  Found {payroll_count} payroll records")

print("[3/6] Checking driver_employee_mapping...")
cur.execute("SELECT COUNT(*) FROM driver_employee_mapping WHERE employee_id = ANY(%s)", (deleted_ids,))
mapping_count = cur.fetchone()[0]
print(f"  Found {mapping_count} mapping records")

print("[4/6] Checking employee_expenses...")
cur.execute("SELECT COUNT(*) FROM employee_expenses WHERE employee_id = ANY(%s)", (deleted_ids,))
expense_count = cur.fetchone()[0]
print(f"  Found {expense_count} expense records")

print("[5/6] Checking driver_documents...")
cur.execute("SELECT COUNT(*) FROM driver_documents WHERE employee_id = ANY(%s)", (deleted_ids,))
doc_count = cur.fetchone()[0]
print(f"  Found {doc_count} document records")

print("[6/6] Checking employee_work_classifications...")
cur.execute("SELECT COUNT(*) FROM employee_work_classifications WHERE employee_id = ANY(%s)", (deleted_ids,))
class_count = cur.fetchone()[0]
print(f"  Found {class_count} classification records")

# Now delete in proper order
print(f"\n{'='*100}")
print("DELETING FK REFERENCES AND EMPLOYEE RECORDS")
print("="*100 + "\n")

if charter_count > 0:
    print(f"[1] Nulling {charter_count} charter assignments...")
    cur.execute("UPDATE charters SET assigned_driver_id = NULL WHERE assigned_driver_id = ANY(%s)", (deleted_ids,))
    print(f"  ✓ Updated {cur.rowcount} charters")

if payroll_count > 0:
    print(f"[2] Deleting {payroll_count} payroll records...")
    cur.execute("DELETE FROM driver_payroll WHERE employee_id = ANY(%s)", (deleted_ids,))
    print(f"  ✓ Deleted {cur.rowcount} payroll records")

if mapping_count > 0:
    print(f"[3] Deleting {mapping_count} driver mappings...")
    cur.execute("DELETE FROM driver_employee_mapping WHERE employee_id = ANY(%s)", (deleted_ids,))
    print(f"  ✓ Deleted {cur.rowcount} mapping records")

if expense_count > 0:
    print(f"[4] Deleting {expense_count} expenses...")
    cur.execute("DELETE FROM employee_expenses WHERE employee_id = ANY(%s)", (deleted_ids,))
    print(f"  ✓ Deleted {cur.rowcount} expense records")

if doc_count > 0:
    print(f"[5] Deleting {doc_count} documents...")
    cur.execute("DELETE FROM driver_documents WHERE employee_id = ANY(%s)", (deleted_ids,))
    print(f"  ✓ Deleted {cur.rowcount} document records")

if class_count > 0:
    print(f"[6] Deleting {class_count} classifications...")
    cur.execute("DELETE FROM employee_work_classifications WHERE employee_id = ANY(%s)", (deleted_ids,))
    print(f"  ✓ Deleted {cur.rowcount} classification records")

# Final delete of employees
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
print(f"  Final employee count: {final_count}")
print("="*100 + "\n")

conn.close()
