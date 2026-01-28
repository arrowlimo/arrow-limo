import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*100)
print("STANDARDIZING ALL EMPLOYEE NAMES TO 'Last, First' FORMAT")
print("="*100 + "\n")

# Get all employees
cur.execute("""
    SELECT employee_id, full_name, first_name, last_name
    FROM employees
    ORDER BY employee_id
""")

all_employees = cur.fetchall()

updates = []

for emp_id, full_name, first_name, last_name in all_employees:
    if not full_name or full_name.strip() == '':
        continue
    
    name_clean = full_name.strip()
    
    # Already in "Last, First" format - keep as is
    if ',' in name_clean:
        # Already standardized
        standardized = name_clean
    else:
        # "First Last" or "First Middle Last" - convert to "Last, First Middle"
        parts = name_clean.split()
        if len(parts) == 1:
            standardized = parts[0]  # Single name, leave as is
        elif len(parts) == 2:
            # "First Last" -> "Last, First"
            standardized = f"{parts[1]}, {parts[0]}"
        else:
            # "First Middle Last" -> "Last, First Middle"
            last = parts[-1]
            first_middle = ' '.join(parts[:-1])
            standardized = f"{last}, {first_middle}"
    
    # Check if we need to update
    if standardized != full_name:
        updates.append({
            'id': emp_id,
            'old': full_name,
            'new': standardized
        })

print(f"Found {len(updates)} names needing standardization\n")
print("Sample of changes (first 30):\n")
print(f"{'ID':<6} {'Old Format':<40} → {'New Format':<40}")
print("-"*90)

for u in updates[:30]:
    print(f"{u['id']:<6} {u['old']:<40} → {u['new']:<40}")

if len(updates) > 30:
    print(f"\n... and {len(updates) - 30} more")

response = input(f"\nStandardize {len(updates)} names to 'Last, First' format? (yes/no): ").strip().lower()

if response == 'yes':
    print("\n[UPDATING] Standardizing full_name to 'Last, First' format...\n")
    
    updated_count = 0
    for u in updates:
        # Update full_name
        cur.execute("""
            UPDATE employees
            SET full_name = %s
            WHERE employee_id = %s
        """, (u['new'], u['id']))
        updated_count += 1
        
        if updated_count % 20 == 0:
            print(f"  Updated {updated_count}/{len(updates)}...")
    
    conn.commit()
    
    print(f"\n✅ Standardized {updated_count} employee names to 'Last, First' format")
    
    # Now re-parse first_name and last_name from standardized full_name
    print("\n[RE-PARSING] Updating first_name and last_name from standardized full_name...\n")
    
    cur.execute("""
        SELECT employee_id, full_name
        FROM employees
        WHERE full_name IS NOT NULL AND full_name != ''
    """)
    
    all_names = cur.fetchall()
    
    for emp_id, full_name in all_names:
        name_clean = full_name.strip()
        
        if ',' in name_clean:
            # "Last, First Middle" format
            parts = [p.strip() for p in name_clean.split(',', 1)]
            last_name = parts[0]
            first_parts = parts[1].split() if len(parts) > 1 else []
            first_name = first_parts[0] if first_parts else ''
        else:
            # Single name or already parsed
            parts = name_clean.split()
            if len(parts) == 1:
                first_name = parts[0]
                last_name = ''
            else:
                first_name = parts[0]
                last_name = parts[-1]
        
        cur.execute("""
            UPDATE employees
            SET first_name = %s, last_name = %s
            WHERE employee_id = %s
        """, (first_name, last_name, emp_id))
    
    conn.commit()
    
    print(f"✅ Re-parsed {len(all_names)} employee names")
    
    # Show sample
    print("\nSample verification (first 10):")
    cur.execute("""
        SELECT employee_id, full_name, first_name, last_name
        FROM employees
        ORDER BY employee_id
        LIMIT 10
    """)
    
    print(f"\n{'ID':<6} {'Full Name':<35} {'First':<15} {'Last':<15}")
    print("-"*75)
    for row in cur.fetchall():
        print(f"{row[0]:<6} {row[1]:<35} {row[2] or '':<15} {row[3] or '':<15}")
    
else:
    print("\n❌ Cancelled")

conn.close()
