import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("FINAL CLEANUP: Delete remaining 4 garbage + 5 duplicate employees")
print("="*100 + "\n")

# Step 1: Delete/NULL all FK references for the 4 garbage records
garbage_ids = [127, 201, 202, 213]  # Dead Employee File, Phone numbers, Email, PO Box

print("STEP 1: Removing FK references for 4 garbage records\n")
for emp_id in garbage_ids:
    cur.execute("SELECT full_name FROM employees WHERE employee_id = %s", (emp_id,))
    name = cur.fetchone()[0]
    
    # Delete/update all FK references
    cur.execute("UPDATE charters SET assigned_driver_id = NULL WHERE assigned_driver_id = %s", (emp_id,))
    charters_updated = cur.rowcount
    
    cur.execute("DELETE FROM driver_payroll WHERE employee_id = %s", (emp_id,))
    payroll_deleted = cur.rowcount
    
    cur.execute("DELETE FROM driver_employee_mapping WHERE employee_id = %s", (emp_id,))
    mapping_deleted = cur.rowcount
    
    cur.execute("DELETE FROM driver_documents WHERE employee_id = %s", (emp_id,))
    docs_deleted = cur.rowcount
    
    cur.execute("DELETE FROM employee_expenses WHERE employee_id = %s", (emp_id,))
    expenses_deleted = cur.rowcount
    
    cur.execute("DELETE FROM employee_work_classifications WHERE employee_id = %s", (emp_id,))
    work_class_deleted = cur.rowcount
    
    cur.execute("DELETE FROM driver_floats WHERE employee_id = %s", (emp_id,))
    floats_deleted = cur.rowcount
    
    total_deleted = payroll_deleted + mapping_deleted + docs_deleted + expenses_deleted + work_class_deleted + floats_deleted
    
    print(f"  ID {emp_id:3d} '{name[:50]:50s}' | Nulled: {charters_updated} charters | Deleted: {total_deleted} related records")

conn.commit()

# Step 2: Delete the 4 garbage records
print("\nSTEP 2: Deleting 4 garbage records\n")
cur.execute("DELETE FROM employees WHERE employee_id IN (%s, %s, %s, %s)", garbage_ids)
deleted = cur.rowcount
print(f"  ✓ Deleted {deleted} garbage records")
conn.commit()

# Step 3: Merge duplicate employees
print("\nSTEP 3: Merging 5 duplicate employees\n")

duplicates = [
    (25, 211, "Crystal Matychuk"),     # Keep 25, delete 211
    (135, 151, "Tammy Pettitt"),        # Keep 135, delete 151
    (55, 1977, "Michael Blades"),       # Keep 55, delete 1977
    (60, 1978, "Wesley Charles"),       # Keep 60, delete 1978
    (1, 1980, "Robert Ferguson"),       # Keep 1, delete 1980
]

for keep_id, delete_id, name in duplicates:
    # Move any charters from delete_id to keep_id
    cur.execute("UPDATE charters SET assigned_driver_id = %s WHERE assigned_driver_id = %s", (keep_id, delete_id))
    charters_moved = cur.rowcount
    
    # Move any payroll from delete_id to keep_id
    cur.execute("UPDATE driver_payroll SET employee_id = %s WHERE employee_id = %s", (keep_id, delete_id))
    payroll_moved = cur.rowcount
    
    # Delete the duplicate
    cur.execute("DELETE FROM employees WHERE employee_id = %s", (delete_id,))
    
    print(f"  {name:20s} | Kept ID {keep_id:4d}, deleted ID {delete_id:4d} | Moved: {charters_moved} charters, {payroll_moved} payroll")

conn.commit()

# Final verification
cur.execute("SELECT COUNT(*) FROM employees")
final_count = cur.fetchone()[0]

print("\n" + "="*100)
print(f"✅ CLEANUP COMPLETE")
print("="*100)
print(f"  Before:  1,003 employees")
print(f"  After:   {final_count} employees")
print(f"  Removed: {1003 - final_count} garbage/duplicate records")
print("="*100)

conn.close()
