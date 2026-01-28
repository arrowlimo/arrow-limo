import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*100)
print("IDENTIFYING GARBAGE EMPLOYEE RECORDS FOR DELETION")
print("="*100 + "\n")

# Find all garbage records (QB artifacts, addresses, metadata, etc.)
cur.execute("""
    SELECT employee_id, full_name
    FROM employees
    WHERE 
        -- QB import artifacts
        full_name ILIKE '%Employee%name:%'
        OR full_name ILIKE '%Gross payroll%'
        OR full_name ILIKE '%Federal Income Tax%'
        OR full_name ILIKE '%CPP - Employee%'
        OR full_name ILIKE '%EI - Employee%'
        OR full_name ILIKE '%Employee Wages%'
        OR full_name ILIKE '%Insurable earnings%'
        OR full_name ILIKE '%Hours - Salary%'
        OR full_name ILIKE '%Employee Earnings%'
        OR full_name ILIKE '%Employee Contact%'
        OR full_name ILIKE '%Employee complaints%'
        OR full_name LIKE 'Dr%Wages%'
        OR full_name LIKE 'Emp.%'
        -- Address fragments
        OR full_name ILIKE '%Street%'
        OR full_name ILIKE '%Avenue%'
        OR full_name ILIKE '%Crescent%'
        OR full_name ILIKE '%Red Deer%'
        OR full_name ILIKE '%Canada%'
        OR full_name ILIKE 'PO Box%'
        OR full_name ILIKE 'AB%'
        -- Metadata fragments
        OR full_name ILIKE 'Email'
        OR full_name ILIKE 'Phone%'
        OR full_name ILIKE 'Address'
        OR full_name ILIKE '%Employee File%'
        -- Empty/invalid
        OR TRIM(COALESCE(full_name, '')) = ''
    ORDER BY employee_id
""")

garbage_records = cur.fetchall()
print(f"Found {len(garbage_records)} potential garbage records\n")

# Now check which ones have FK references
print("Checking for foreign key references...\n")

safe_to_delete = []
has_references = []

for emp_id, full_name in garbage_records:
    # Check all FK tables
    cur.execute("""
        SELECT 
            (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = %s) +
            (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = %s) +
            (SELECT COUNT(*) FROM employee_expenses WHERE employee_id = %s) +
            (SELECT COUNT(*) FROM driver_documents WHERE employee_id = %s) +
            (SELECT COUNT(*) FROM employee_work_classifications WHERE employee_id = %s) as total_refs
    """, (emp_id, emp_id, emp_id, emp_id, emp_id))
    
    total_refs = cur.fetchone()[0]
    
    if total_refs == 0:
        safe_to_delete.append((emp_id, full_name))
    else:
        has_references.append((emp_id, full_name, total_refs))

print(f"✓ Safe to delete (no FK references): {len(safe_to_delete)}")
print(f"✗ Has FK references (cannot delete): {len(has_references)}\n")

if has_references:
    print("Records with FK references (KEEP these):")
    for emp_id, name, refs in has_references[:20]:
        print(f"  ID {emp_id:4d} | {refs:4d} refs | {name[:70]}")
    if len(has_references) > 20:
        print(f"  ... and {len(has_references)-20} more")

print(f"\n{'='*100}")
print(f"DELETION PLAN:")
print(f"{'='*100}")
print(f"  Total garbage records found:     {len(garbage_records)}")
print(f"  Safe to delete (no FKs):         {len(safe_to_delete)}")
print(f"  Must keep (has FKs):             {len(has_references)}")
print(f"  Database after cleanup:          {1003 - len(safe_to_delete)} employees")
print(f"{'='*100}\n")

# Show sample of what will be deleted
print("Sample of records to be DELETED (first 30):\n")
for emp_id, name in safe_to_delete[:30]:
    print(f"  ID {emp_id:4d} | {name[:80]}")
if len(safe_to_delete) > 30:
    print(f"  ... and {len(safe_to_delete)-30} more")

# Ask for confirmation
print(f"\n{'='*100}")
response = input(f"\nDelete {len(safe_to_delete)} garbage employee records? (yes/no): ").strip().lower()

if response == 'yes':
    print("\n[DELETING] Garbage records...")
    
    # Delete in batches
    ids_to_delete = [emp_id for emp_id, _ in safe_to_delete]
    
    # Use IN clause for batch delete
    if ids_to_delete:
        placeholders = ','.join(['%s'] * len(ids_to_delete))
        cur.execute(f"DELETE FROM employees WHERE employee_id IN ({placeholders})", ids_to_delete)
        deleted = cur.rowcount
        conn.commit()
        
        print(f"✅ Deleted {deleted} garbage employee records")
        
        # Verify
        cur.execute("SELECT COUNT(*) FROM employees")
        remaining = cur.fetchone()[0]
        print(f"\nEmployees remaining in database: {remaining}")
    else:
        print("No records to delete")
else:
    print("\n❌ Cancelled")

conn.close()
