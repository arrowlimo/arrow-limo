import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*80)
print("EMPLOYEE DUPLICATION ANALYSIS")
print("="*80 + "\n")

# 1. Duplicate full names
print("1. DUPLICATE FULL NAMES:\n")
cur.execute("""
    SELECT full_name, COUNT(*) as count, STRING_AGG(employee_id::text, ', ') as ids
    FROM employees
    WHERE TRIM(COALESCE(full_name, '')) != ''
    GROUP BY full_name
    HAVING COUNT(*) > 1
    ORDER BY count DESC, full_name
""")

dups = cur.fetchall()
if dups:
    for name, count, ids in dups:
        print(f"  {name:40s} | {count} copies | IDs: {ids}")
    print(f"\n  Total duplicate name groups: {len(dups)}")
else:
    print("  ✓ No duplicate full names found")

# 2. Duplicate first+last combinations
print("\n\n2. DUPLICATE FIRST+LAST NAME COMBINATIONS:\n")
cur.execute("""
    SELECT first_name, last_name, COUNT(*) as count, STRING_AGG(employee_id::text, ', ') as ids
    FROM employees
    WHERE TRIM(COALESCE(first_name, '')) != '' 
    AND TRIM(COALESCE(last_name, '')) != ''
    GROUP BY first_name, last_name
    HAVING COUNT(*) > 1
    ORDER BY count DESC
""")

dups2 = cur.fetchall()
if dups2:
    for fname, lname, count, ids in dups2:
        print(f"  {fname} {lname:35s} | {count} copies | IDs: {ids}")
    print(f"\n  Total duplicate first+last groups: {len(dups2)}")
else:
    print("  ✓ No duplicate first+last combinations found")

# 3. Same QuickBooks ID
print("\n\n3. DUPLICATE QUICKBOOKS IDs:\n")
cur.execute("""
    SELECT quickbooks_id, COUNT(*) as count, STRING_AGG(full_name || ' (ID:' || employee_id::text || ')', ', ') as employees
    FROM employees
    WHERE quickbooks_id IS NOT NULL
    GROUP BY quickbooks_id
    HAVING COUNT(*) > 1
    ORDER BY count DESC
""")

dups3 = cur.fetchall()
if dups3:
    for qb_id, count, employees in dups3:
        print(f"  QB ID {qb_id}: {count} employees")
        print(f"    {employees}")
else:
    print("  ✓ No duplicate QuickBooks IDs")

# 4. Same driver_code
print("\n\n4. DUPLICATE DRIVER CODES:\n")
cur.execute("""
    SELECT driver_code, COUNT(*) as count, STRING_AGG(full_name || ' (ID:' || employee_id::text || ')', ', ') as employees
    FROM employees
    WHERE driver_code IS NOT NULL AND TRIM(driver_code) != ''
    GROUP BY driver_code
    HAVING COUNT(*) > 1
    ORDER BY count DESC
""")

dups4 = cur.fetchall()
if dups4:
    for code, count, employees in dups4[:20]:
        print(f"  Code '{code}': {count} employees")
        print(f"    {employees}")
    if len(dups4) > 20:
        print(f"  ... and {len(dups4)-20} more duplicate driver codes")
else:
    print("  ✓ No duplicate driver codes")

# 5. Find employees with same name but slight variations
print("\n\n5. POTENTIAL NAME VARIATIONS (fuzzy matches):\n")
cur.execute("""
    SELECT 
        e1.employee_id as id1,
        e1.full_name as name1,
        e2.employee_id as id2,
        e2.full_name as name2
    FROM employees e1
    JOIN employees e2 ON e1.employee_id < e2.employee_id
    WHERE 
        LOWER(REGEXP_REPLACE(e1.full_name, '[^a-z]', '', 'g')) = 
        LOWER(REGEXP_REPLACE(e2.full_name, '[^a-z]', '', 'g'))
        AND e1.full_name != e2.full_name
    ORDER BY e1.full_name
    LIMIT 50
""")

fuzzy = cur.fetchall()
if fuzzy:
    for id1, name1, id2, name2 in fuzzy:
        print(f"  ID {id1:3d}: '{name1}' ≈ ID {id2:3d}: '{name2}'")
    if len(fuzzy) == 50:
        print(f"  ... (showing first 50 matches)")
else:
    print("  ✓ No fuzzy name matches found")

print("\n" + "="*80)
print("SUMMARY:")
print(f"  Exact name duplicates:       {len(dups)}")
print(f"  First+Last duplicates:       {len(dups2)}")
print(f"  QuickBooks ID duplicates:    {len(dups3)}")
print(f"  Driver code duplicates:      {len(dups4)}")
print(f"  Fuzzy name variations:       {len(fuzzy)}")
print("="*80)
