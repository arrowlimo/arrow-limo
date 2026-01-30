import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

# Find names with periods that might be typos
cur.execute("""
    SELECT employee_id, full_name, first_name, last_name
    FROM employees
    WHERE full_name LIKE '%.%'
      AND full_name NOT LIKE '%,%'
    ORDER BY full_name
""")

rows = cur.fetchall()

print(f"\nFound {len(rows)} employee names with periods:\n")
print(f"{'ID':<6} {'Full Name':<40} {'First':<15} {'Last':<15} {'Issue'}")
print("-"*100)

for emp_id, full, first, last in rows:
    # Check if period is part of middle initial (OK) or a typo
    if full.endswith('.'):
        issue = "❌ Trailing period (typo)"
    elif ' .' in full:
        issue = "❌ Period after space (typo)"  
    elif '. ' in full and not any(x in full for x in ['Jr.', 'Sr.', 'Dr.', 'Mr.', 'Mrs.', 'Ms.']):
        # Check if it's a middle initial
        parts = full.split()
        if len(parts) >= 3 and len(parts[1]) == 2 and parts[1].endswith('.'):
            issue = "✓ Middle initial (OK)"
        else:
            issue = "❓ Check if valid"
    else:
        issue = "✓ Likely OK (title/abbrev)"
    
    print(f"{emp_id:<6} {full:<40} {first or '':<15} {last or '':<15} {issue}")

conn.close()
