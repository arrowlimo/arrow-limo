import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("FINDING DUPLICATE EMPLOYEES (DR/H/OF numbered vs name-only)")
print("="*100 + "\n")

# Get all employees
cur.execute("""
    SELECT employee_id, full_name, employee_number, first_name, last_name, position,
           is_chauffeur, salary, tax_exemptions,
           (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll_count,
           (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charter_count
    FROM employees
    ORDER BY employee_id
""")

all_emps = cur.fetchall()

# Build name lookup
name_to_employees = {}
for emp in all_emps:
    emp_id, full_name, emp_num, first, last, pos, chauffeur, sal, tax, pay, chrt = emp
    
    # Normalize name for matching
    name_key = full_name.lower().strip().replace(',', '').replace('.', '')
    
    if name_key not in name_to_employees:
        name_to_employees[name_key] = []
    name_to_employees[name_key].append(emp)

# Find duplicates
duplicates = []
for name_key, emps in name_to_employees.items():
    if len(emps) > 1:
        # Check if one has DR/H/OF number and one doesn't
        has_code = [e for e in emps if e[2] and (e[2].upper().startswith('DR') or e[2].upper().startswith('H') or e[2].upper().startswith('OF'))]
        no_code = [e for e in emps if not e[2] or not (e[2].upper().startswith('DR') or e[2].upper().startswith('H') or e[2].upper().startswith('OF'))]
        
        if has_code and no_code:
            duplicates.append((name_key, has_code, no_code))

print(f"Found {len(duplicates)} potential duplicate groups\n")

to_delete = []

for name_key, with_code, without_code in duplicates:
    print(f"\n{name_key.upper()}:")
    
    # Show all versions
    for emp in with_code:
        emp_id, full_name, emp_num, first, last, pos, chauffeur, sal, tax, pay, chrt = emp
        print(f"  ID {emp_id:4d} | {emp_num:10s} | P:{pay:3d} C:{chrt:4d} | {full_name}")
    
    for emp in without_code:
        emp_id, full_name, emp_num, first, last, pos, chauffeur, sal, tax, pay, chrt = emp
        emp_num_display = emp_num if emp_num else "(no code)"
        print(f"  ID {emp_id:4d} | {emp_num_display:10s} | P:{pay:3d} C:{chrt:4d} | {full_name}")
    
    # Determine which to keep
    # Keep the one with the most data (payroll + charters)
    all_versions = with_code + without_code
    all_versions.sort(key=lambda x: (x[9] + x[10]), reverse=True)  # Sort by payroll + charter count
    
    keep = all_versions[0]
    delete = all_versions[1:]
    
    print(f"  → KEEP: ID {keep[0]} ({keep[9]} payroll + {keep[10]} charters)")
    for d in delete:
        print(f"  → DELETE: ID {d[0]} ({d[9]} payroll + {d[10]} charters)")
        to_delete.append(d[0])

print(f"\n{'='*100}")
print(f"SUMMARY:")
print(f"  Duplicate groups found: {len(duplicates)}")
print(f"  Employee IDs to delete: {len(to_delete)}")
print(f"{'='*100}\n")

if to_delete:
    response = input(f"Delete {len(to_delete)} duplicate employee records? (yes/no): ").strip().lower()
    
    if response == 'yes':
        print("\n[MERGING] Moving data from duplicates to primary records...\n")
        
        for dup_id in to_delete:
            # Find the duplicate and primary
            dup = [e for e in all_emps if e[0] == dup_id][0]
            
            # Find primary (same name, not in delete list)
            name_key = dup[1].lower().strip().replace(',', '').replace('.', '')
            primary_candidates = [e for e in name_to_employees[name_key] if e[0] not in to_delete]
            if primary_candidates:
                primary = primary_candidates[0]
                
                # Move charters
                cur.execute("UPDATE charters SET assigned_driver_id = %s WHERE assigned_driver_id = %s", (primary[0], dup_id))
                charters_moved = cur.rowcount
                
                # Move payroll
                cur.execute("UPDATE driver_payroll SET employee_id = %s WHERE employee_id = %s", (primary[0], dup_id))
                payroll_moved = cur.rowcount
                
                # Delete the duplicate
                cur.execute("DELETE FROM employees WHERE employee_id = %s", (dup_id,))
                
                print(f"  ✓ Merged ID {dup_id:4d} → ID {primary[0]:4d} | Moved {charters_moved} charters, {payroll_moved} payroll")
        
        conn.commit()
        
        cur.execute("SELECT COUNT(*) FROM employees")
        final = cur.fetchone()[0]
        
        print(f"\n✅ Deleted {len(to_delete)} duplicates")
        print(f"Final employee count: {final}")
    else:
        print("\n❌ Cancelled")
else:
    print("No duplicates to delete")

conn.close()
