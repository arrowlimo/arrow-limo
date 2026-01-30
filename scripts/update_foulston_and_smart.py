import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

print("\n" + "="*80)
print("EMPLOYEE UPDATES")
print("="*80)

# 1. Mark Tabatha Foulston as inactive
print("\n1. Marking Tabatha Foulston as inactive (quit)...")
cur.execute("""
    UPDATE employees
    SET status = 'inactive'
    WHERE full_name = 'Foulston, Tabatha'
""")
conn.commit()
print(f"   ✅ Marked Tabatha Foulston (DR104) as inactive")

# 2. Check Liisa Smart spelling
print("\n2. Checking Liisa Smart spelling...")
cur.execute("""
    SELECT employee_id, employee_number, full_name, first_name, last_name
    FROM employees
    WHERE full_name LIKE '%Smart%'
""")

result = cur.fetchone()
if result:
    print(f"   Current: {result[2]}")
    print(f"   First: {result[3]}, Last: {result[4]}")
    print(f"\n   Note: 'Liisa' is Finnish/Estonian spelling (double 'i')")
    print(f"   Common alternate: 'Lisa' (single 'i')")
    
    response = input(f"\n   Change 'Liisa' to 'Lisa'? (yes/no): ").strip().lower()
    
    if response == 'yes':
        cur.execute("""
            UPDATE employees
            SET full_name = 'Smart, Lisa', first_name = 'Lisa'
            WHERE employee_id = %s
        """, (result[0],))
        conn.commit()
        print(f"   ✅ Updated to 'Smart, Lisa'")
    else:
        print(f"   ℹ️  Kept as 'Liisa' (Finnish spelling)")

# Show current active driver count
cur.execute("""
    SELECT COUNT(*) 
    FROM employees 
    WHERE is_chauffeur = TRUE AND status = 'active'
""")
active_count = cur.fetchone()[0]

print(f"\n{'='*80}")
print(f"Active drivers now: {active_count}")
print(f"{'='*80}\n")

conn.close()
