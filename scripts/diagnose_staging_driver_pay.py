import os, psycopg2
from collections import Counter

conn = psycopg2.connect(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***')
)
cur = conn.cursor()

print("=" * 80)
print("STAGING_DRIVER_PAY ANALYSIS")
print("=" * 80)

# 1. Sample records to understand structure
print("\n1. SAMPLE RECORDS (showing data patterns)")
print("-" * 80)
cur.execute("""
    SELECT id, file_id, source_row_id, source_line_no, txn_date, driver_name, 
           driver_id, pay_type, gross_amount, net_amount, memo, source_file
    FROM staging_driver_pay
    WHERE driver_name IS NOT NULL AND driver_name != ''
    ORDER BY file_id, source_line_no
    LIMIT 20
""")

for row in cur.fetchall():
    print(f"ID {row[0]}: File {row[1]} | Line {row[3]} | Date {row[4]} | Name '{row[5]}' | Type '{row[7]}' | Gross ${row[8]} | Net ${row[9]}")
    if row[11]:
        print(f"  Source: {row[11]}")

# 2. Check for date-like values in driver_name (data shift issue)
print("\n2. DATE-LIKE VALUES IN DRIVER_NAME (column shift detection)")
print("-" * 80)
cur.execute("""
    SELECT driver_name, COUNT(*) as cnt
    FROM staging_driver_pay
    WHERE driver_name ~ '^\d{1,2}/\d{1,2}/\d{4}$'
    GROUP BY driver_name
    ORDER BY cnt DESC
    LIMIT 10
""")

date_patterns = cur.fetchall()
if date_patterns:
    print("Found date patterns in driver_name field (indicates column shift):")
    for name, cnt in date_patterns:
        print(f"  '{name}': {cnt:,} rows")
else:
    print("No date patterns found")

# 3. Analyze driver_name distribution
print("\n3. DRIVER NAME DISTRIBUTION")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_rows,
        COUNT(DISTINCT driver_name) as unique_names,
        COUNT(*) FILTER (WHERE driver_name IS NULL OR driver_name = '') as null_names,
        COUNT(*) FILTER (WHERE driver_name ~ '^\d') as starts_with_digit,
        COUNT(*) FILTER (WHERE LENGTH(driver_name) > 50) as very_long_names
    FROM staging_driver_pay
""")

total, unique, nulls, digits, long_names = cur.fetchone()
print(f"Total rows: {total:,}")
print(f"Unique driver names: {unique:,}")
print(f"NULL/empty names: {nulls:,} ({nulls/total*100:.1f}%)")
print(f"Starts with digit: {digits:,} ({digits/total*100:.1f}%)")
print(f"Very long names (>50 chars): {long_names:,}")

# 4. Top driver names
print("\n4. TOP 20 DRIVER NAMES (by frequency)")
print("-" * 80)
cur.execute("""
    SELECT driver_name, COUNT(*) as cnt
    FROM staging_driver_pay
    WHERE driver_name IS NOT NULL AND driver_name != ''
    GROUP BY driver_name
    ORDER BY cnt DESC
    LIMIT 20
""")

for name, cnt in cur.fetchall():
    print(f"  {name:<40} {cnt:>6,} rows")

# 5. Check staging_driver_pay_files for source file metadata
print("\n5. SOURCE FILE METADATA")
print("-" * 80)
cur.execute("""
    SELECT file_id, file_name, file_path, row_count, imported_at, status
    FROM staging_driver_pay_files
    ORDER BY imported_at DESC
    LIMIT 10
""")

print("Recent file imports:")
for file_id, name, path, rows, imported, status in cur.fetchall():
    print(f"  File {file_id}: {name} | {rows:,} rows | {imported} | Status: {status}")

# 6. Check for valid employee names in employees table
print("\n6. EMPLOYEE NAME PATTERNS (for fuzzy matching)")
print("-" * 80)
cur.execute("""
    SELECT 
        COUNT(*) as total_employees,
        COUNT(DISTINCT full_name) as unique_names,
        COUNT(*) FILTER (WHERE status = 'active') as active_employees
    FROM employees
    WHERE full_name IS NOT NULL
""")

emp_total, emp_unique, active = cur.fetchone()
print(f"Total employees: {emp_total:,}")
print(f"Unique full names: {emp_unique:,}")
print(f"Active employees: {active:,}")

# Sample employee names
cur.execute("""
    SELECT full_name
    FROM employees
    WHERE full_name IS NOT NULL
    ORDER BY employee_id
    LIMIT 20
""")

print("\nSample employee names:")
for (name,) in cur.fetchall():
    print(f"  {name}")

# 7. Check if any staging records have valid-looking names
print("\n7. POTENTIAL NAME MATCHES (staging names vs employees)")
print("-" * 80)
cur.execute("""
    SELECT DISTINCT s.driver_name
    FROM staging_driver_pay s
    WHERE EXISTS (
        SELECT 1 FROM employees e
        WHERE LOWER(TRIM(s.driver_name)) = LOWER(TRIM(e.full_name))
    )
    LIMIT 20
""")

matches = cur.fetchall()
if matches:
    print(f"Found {len(matches)} staging driver_names with exact employee matches:")
    for (name,) in matches:
        print(f"  {name}")
else:
    print("No exact matches found between staging driver_name and employee full_name")

print("\n" + "=" * 80)
print("DIAGNOSIS")
print("=" * 80)
print("""
Key Findings:
1. Check if driver_name contains dates (column shift during import)
2. Check if gross_amount/net_amount are in wrong columns
3. Identify valid name patterns for fuzzy matching
4. Determine if source files need re-import or data needs column correction

Next Steps:
- If column shift detected: Create column realignment script
- If names are valid: Build fuzzy name matcher
- If amounts are missing: Re-import from source files
""")

cur.close()
conn.close()
