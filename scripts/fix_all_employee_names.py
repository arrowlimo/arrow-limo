import psycopg2
import re

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

print("\n" + "="*100)
print("FIXING FIRST_NAME AND LAST_NAME COLUMNS FOR ALL EMPLOYEES")
print("="*100 + "\n")

# Get all employees
cur.execute("""
    SELECT employee_id, full_name, first_name, last_name
    FROM employees
    ORDER BY employee_id
""")

all_employees = cur.fetchall()

updates = []

for emp_id, full_name, current_first, current_last in all_employees:
    if not full_name or full_name.strip() == '':
        continue
    
    # Parse the full_name
    name_clean = full_name.strip()
    
    # Handle different formats:
    # "Last, First Middle" or "First Middle Last" or "First Last"
    
    if ',' in name_clean:
        # Format: "Last, First Middle"
        parts = [p.strip() for p in name_clean.split(',')]
        last_name = parts[0]
        first_parts = parts[1].split() if len(parts) > 1 else []
        first_name = first_parts[0] if first_parts else ''
        middle_name = ' '.join(first_parts[1:]) if len(first_parts) > 1 else ''
    else:
        # Format: "First Middle Last" or "First Last"
        parts = name_clean.split()
        if len(parts) == 1:
            first_name = parts[0]
            middle_name = ''
            last_name = ''
        elif len(parts) == 2:
            first_name = parts[0]
            middle_name = ''
            last_name = parts[1]
        else:
            # 3+ parts: assume "First Middle... Last"
            first_name = parts[0]
            last_name = parts[-1]
            middle_name = ' '.join(parts[1:-1])
    
    # Clean up trailing commas
    last_name = last_name.rstrip(',')
    first_name = first_name.rstrip(',')
    
    # Check if we need to update
    if first_name != current_first or last_name != current_last:
        updates.append({
            'id': emp_id,
            'full_name': full_name,
            'old_first': current_first or '(none)',
            'old_last': current_last or '(none)',
            'new_first': first_name,
            'new_last': last_name,
            'middle': middle_name
        })

print(f"Found {len(updates)} employees needing name fixes\n")
print("Sample of changes (first 20):\n")
print(f"{'ID':<6} {'Full Name':<30} {'Old First':<15} → {'New First':<15} | {'Old Last':<15} → {'New Last':<15} | {'Middle':<15}")
print("-"*130)

for u in updates[:20]:
    print(f"{u['id']:<6} {u['full_name']:<30} {u['old_first']:<15} → {u['new_first']:<15} | {u['old_last']:<15} → {u['new_last']:<15} | {u['middle']:<15}")

print(f"\n... and {len(updates) - 20} more" if len(updates) > 20 else "")

response = input(f"\nApply {len(updates)} name fixes? (yes/no): ").strip().lower()

if response == 'yes':
    print("\n[UPDATING] Fixing first_name and last_name columns...\n")
    
    updated_count = 0
    for u in updates:
        cur.execute("""
            UPDATE employees
            SET first_name = %s, last_name = %s
            WHERE employee_id = %s
        """, (u['new_first'], u['new_last'], u['id']))
        updated_count += 1
        
        if updated_count % 50 == 0:
            print(f"  Updated {updated_count}/{len(updates)}...")
    
    conn.commit()
    
    print(f"\n✅ Updated {updated_count} employee records")
    print(f"   Fixed first_name and last_name columns")
    
    # Show sample of corrected records
    print("\nSample verification (first 10):")
    cur.execute("""
        SELECT employee_id, full_name, first_name, last_name
        FROM employees
        ORDER BY employee_id
        LIMIT 10
    """)
    
    print(f"\n{'ID':<6} {'Full Name':<30} {'First':<15} {'Last':<15}")
    print("-"*70)
    for row in cur.fetchall():
        print(f"{row[0]:<6} {row[1]:<30} {row[2] or '(none)':<15} {row[3] or '(none)':<15}")
    
else:
    print("\n❌ Cancelled")

conn.close()
