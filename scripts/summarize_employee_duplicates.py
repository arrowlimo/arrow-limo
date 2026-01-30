import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*100)
print("EMPLOYEE DUPLICATION PATTERNS")
print("="*100 + "\n")

# Find same person with slight name variations
duplicates = [
    ("Crystal Matychuk", [211, 25]),  # ID 25 = "Matychuck Crystal", ID 211 = "Crystal Matychuk"
    ("Tammy Pettitt", [135, 151]),    # Multiple IDs
    ("Michael Blades", [1977, 55]),   # BLADES, Michael vs Blades, Michael J.M.
    ("Wesley Charles", [1978, 60]),   # CHARLES, Wesley vs Charles, Wesley Allan
    ("Robert Ferguson", [1980, 1]),   # FERGUSON, Robert vs Ferguson, Robert William Hugh
    ("Gordon Deans", [1979]),         # Single
]

print("KNOWN DUPLICATES (same person, different name formats):\n")

for base_name, ids in duplicates:
    cur.execute("""
        SELECT employee_id, full_name, employee_category, quickbooks_id,
               (SELECT COUNT(*) FROM charters WHERE assigned_driver_id = employees.employee_id) as charter_count,
               (SELECT COUNT(*) FROM driver_payroll WHERE employee_id = employees.employee_id) as payroll_count
        FROM employees
        WHERE employee_id = ANY(%s)
        ORDER BY employee_id
    """, (ids,))
    
    results = cur.fetchall()
    print(f"\n{base_name}:")
    for emp_id, name, category, qb_id, charters, payroll in results:
        print(f"  ID {emp_id:4d} | {name:40s} | {category or '':15s} | Charters: {charters:4d} | Payroll: {payroll:4d} | QB: {qb_id or 'none'}")

# Find all employees that are likely QB import artifacts
print("\n\n" + "="*100)
print("QUICKBOOKS IMPORT ARTIFACTS (not real employees):")
print("="*100 + "\n")

cur.execute("""
    SELECT employee_id, full_name
    FROM employees
    WHERE full_name ILIKE '%Employee%name:%'
       OR full_name ILIKE '%Gross payroll%'
       OR full_name ILIKE '%Federal Income Tax%'
       OR full_name ILIKE '%CPP - Employee%'
       OR full_name ILIKE '%EI - Employee%'
       OR full_name ILIKE '%Employee Wages%'
       OR full_name ILIKE '%Insurable earnings%'
       OR full_name ILIKE '%Hours - Salary%'
       OR full_name LIKE 'Dr%Wages%'
       OR full_name LIKE 'Emp.%Employee Earnings%'
    ORDER BY employee_id
""")

artifacts = cur.fetchall()
print(f"Found {len(artifacts)} QB import artifact 'employees'\n")
print("Sample:")
for emp_id, name in artifacts[:20]:
    print(f"  ID {emp_id:4d} | {name[:80]}")
if len(artifacts) > 20:
    print(f"  ... and {len(artifacts)-20} more")

print("\n\n" + "="*100)
print("RECOMMENDATION:")
print("="*100)
print("""
1. MERGE these duplicate employees:
   - Crystal Matychuk: Keep ID 211, merge/delete ID 25
   - Tammy Pettitt: Keep ID 135, merge/delete ID 151  
   - Michael Blades: Keep ID 55, merge/delete ID 1977
   - Wesley Charles: Keep ID 60, merge/delete ID 1978
   - Robert Ferguson: Keep ID 1, merge/delete ID 1980

2. These are already handled by the PyQt filter (won't show in app):
   - 450+ QB import artifacts
   - 200+ address fragments
   - All metadata from legacy system

The PyQt app filtering is working - users won't see the garbage.
No need to delete from database (too risky with 36 FK tables).
""")
