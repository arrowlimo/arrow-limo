import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("DELETING REMAINING QB PAYROLL ARTIFACTS")
print("="*100 + "\n")

# Find all remaining junk
cur.execute("""
    SELECT employee_id, full_name
    FROM employees
    WHERE full_name ILIKE '%wages%'
       OR full_name ILIKE '%income tax%'
       OR full_name ILIKE '%salary%'
       OR full_name ILIKE '%gross pay%'
       OR full_name ILIKE '%box %'
       OR full_name ILIKE '%cpp%'
       OR full_name ILIKE '%employee''s%'
       OR full_name ILIKE '%pay period%'
       OR full_name ILIKE '%earnings%'
       OR full_name ILIKE '%withholdings%'
       OR full_name ILIKE '%cheque number%'
       OR full_name ILIKE '%paystub%'
       OR full_name ILIKE '%payroll%'
       OR full_name ILIKE '%deductions%'
       OR full_name ILIKE '%pensionable%'
       OR full_name ILIKE '%taxable income%'
       OR full_name ILIKE '%pay periods%'
       OR full_name ILIKE '%incentive pay%'
       OR full_name ILIKE '%general holiday%'
       OR full_name LIKE '%-%-%'
       OR full_name LIKE 'Dr%Wages%'
       OR full_name LIKE 'H0%'
       OR full_name LIKE 'Of%'
       OR full_name LIKE 'Mobile:%'
       OR full_name LIKE 'Driver D%'
       OR full_name LIKE 'Driver Dr%'
       OR full_name LIKE 'Driver Sales%'
       OR full_name ILIKE '%REALIZING%'
       OR full_name ILIKE '%RECOGNIZING%'
       OR full_name ILIKE '%PAYABLE%'
       OR LENGTH(full_name) > 60
    ORDER BY employee_id
""")

junk = cur.fetchall()
print(f"Found {len(junk)} QB payroll artifact records\n")

# Check which ones have FK references
safe = []
has_refs = []

for emp_id, name in junk:
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = %s) +
            (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = %s) +
            (SELECT COUNT(*) FROM employee_expenses WHERE employee_id = %s) as total
    """, (emp_id, emp_id, emp_id))
    
    refs = cur.fetchone()[0]
    if refs == 0:
        safe.append(emp_id)
    else:
        has_refs.append((emp_id, name, refs))

print(f"Safe to delete (no FKs): {len(safe)}")
print(f"Has FK references: {len(has_refs)}\n")

if has_refs:
    print("Records WITH FK refs (need to handle):\n")
    for emp_id, name, refs in has_refs:
        print(f"  ID {emp_id:4d} | {refs:3d} refs | {name[:70]}")

print(f"\n{'='*100}")
print("DELETION PLAN:")
print(f"  Delete: {len(safe)} safe records")
print(f"  Handle: {len(has_refs)} records with FK references")
print(f"  After:  {614 - len(safe)} employees remaining")
print(f"{'='*100}\n")

if len(safe) > 0:
    response = input(f"Delete {len(safe)} safe junk records? (yes/no): ").strip().lower()
    if response == 'yes':
        # Delete safe records
        placeholders = ','.join(['%s'] * len(safe))
        cur.execute(f"DELETE FROM employees WHERE employee_id IN ({placeholders})", safe)
        deleted = cur.rowcount
        conn.commit()
        
        print(f"\n✅ Deleted {deleted} junk records")
        
        cur.execute("SELECT COUNT(*) FROM employees")
        remaining = cur.fetchone()[0]
        print(f"Employees remaining: {remaining}")
        
        # Now handle the ones with FK refs
        if has_refs:
            print(f"\n{'='*100}")
            print("HANDLING RECORDS WITH FK REFERENCES")
            print(f"{'='*100}\n")
            
            for emp_id, name, refs in has_refs:
                # Delete related records first
                cur.execute("UPDATE charters SET assigned_driver_id = NULL WHERE assigned_driver_id = %s", (emp_id,))
                cur.execute("DELETE FROM driver_payroll WHERE employee_id = %s", (emp_id,))
                cur.execute("DELETE FROM driver_employee_mapping WHERE employee_id = %s", (emp_id,))
                cur.execute("DELETE FROM driver_documents WHERE employee_id = %s", (emp_id,))
                cur.execute("DELETE FROM employee_expenses WHERE employee_id = %s", (emp_id,))
                
                # Now delete the employee
                cur.execute("DELETE FROM employees WHERE employee_id = %s", (emp_id,))
                print(f"  ✓ Deleted ID {emp_id:4d} | {name[:70]}")
            
            conn.commit()
            
            cur.execute("SELECT COUNT(*) FROM employees")
            final = cur.fetchone()[0]
            print(f"\n✅ Final employee count: {final}")
    else:
        print("\n❌ Cancelled")
else:
    print("No safe records to delete")

conn.close()
