#!/usr/bin/env python
"""
Analyze employee records for duplicates, null values, and create a consolidation plan.
Export to JSON for reversible migration.
"""
import psycopg2
import os
import json
from collections import defaultdict

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Get all columns
cur.execute('''
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'employees' ORDER BY ordinal_position
''')
all_cols = [row[0] for row in cur.fetchall()]

# Count total rows
cur.execute('SELECT COUNT(*) FROM employees')
total_rows = cur.fetchone()[0]

# Columns with most NULLs
null_stats = {}
for col in all_cols:
    cur.execute(f'''SELECT COUNT(*) FROM employees WHERE "{col}" IS NULL''')
    null_count = cur.fetchone()[0]
    null_stats[col] = null_count

print("="*80)
print('ANALYSIS: Null Values in almsdata.employees')
print("="*80)
print(f'Total rows: {total_rows}')
print()

print('Top columns with NULL values:')
print('-'*80)
for col, null_count in sorted(null_stats.items(), key=lambda x: -x[1])[:15]:
    pct = (null_count / total_rows * 100) if total_rows > 0 else 0
    print(f'  {col:30s} | {null_count:3d} NULLs ({pct:5.1f}%)')
print()

# Load the 135 real employees from XLS
import xlrd
wb = xlrd.open_workbook(r'L:\limo\reports\New folder (2)\New folder (2)\employeelistbasic.xls')
ws = wb.sheet_by_index(0)
real_emp_numbers = set()
for row_idx in range(1, ws.nrows):
    emp_num = str(ws.cell_value(row_idx, 0)).strip()
    if emp_num and emp_num not in ['Dead Employee File', 'Invoice Purposes']:
        real_emp_numbers.add(emp_num)

print(f'Real employees from XLS: {len(real_emp_numbers)}')
print()

# Categorize employees
cur.execute('''
    SELECT employee_id, employee_number, full_name, 
           CASE WHEN employee_number IN (%s) THEN 'REAL'
                WHEN full_name LIKE '%%Dead%%' OR full_name LIKE '%%Invoice%%' OR full_name LIKE '%%Consulting%%' THEN 'PLACEHOLDER'
                WHEN employee_number LIKE 'LEGACY-%%' THEN 'LEGACY_METADATA'
                WHEN employee_number LIKE '8000%%' OR employee_number LIKE 'QB-%%' THEN 'QBO_IMPORT'
                ELSE 'UNKNOWN'
           END as category
    FROM employees
    ORDER BY category, full_name
''' % ','.join(f"'{e}'" for e in real_emp_numbers))

categories = {}
for emp_id, emp_num, full_name, cat in cur.fetchall():
    if cat not in categories:
        categories[cat] = []
    categories[cat].append((emp_id, emp_num, full_name))

print('Employee categorization:')
print('-'*80)
for cat in sorted(categories.keys()):
    count = len(categories[cat])
    print(f'{cat:20s} | {count:3d} records')
    if count <= 10:
        for emp_id, emp_num, name in categories[cat]:
            print(f'  └─ ID={emp_id:3d} | {emp_num:20s} | {name}')

print()
print("="*80)
print('DEDUPLICATION STRATEGY')
print("="*80)
print()

# Find duplicate names (same person, multiple records)
cur.execute('''
    SELECT full_name, COUNT(*) as cnt, 
           array_agg(employee_id ORDER BY employee_id) as ids,
           array_agg(employee_number ORDER BY employee_number) as numbers
    FROM employees
    WHERE full_name IS NOT NULL AND full_name != ''
    GROUP BY full_name
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
''')

duplicates_by_name = cur.fetchall()
print(f'Found {len(duplicates_by_name)} names with multiple employee records')
print()

if duplicates_by_name:
    print('Top duplicates (same name, multiple IDs):')
    print('-'*80)
    for name, cnt, ids, numbers in duplicates_by_name[:20]:
        print(f'  {name:40s} | {cnt} records | IDs: {ids} | Numbers: {numbers}')
    print()

# Export all employees to JSON (before migration)
cur.execute(f'''
    SELECT {', '.join(f'"{col}"' for col in all_cols)}
    FROM employees
    ORDER BY employee_id
''')

rows = cur.fetchall()
employees_json = []
for row in rows:
    emp_dict = {all_cols[i]: row[i] for i in range(len(all_cols))}
    employees_json.append(emp_dict)

with open('reports/employees_backup_before_migration.json', 'w') as f:
    json.dump(employees_json, f, indent=2, default=str)

print(f'✓ Exported all {len(employees_json)} employee records to employees_backup_before_migration.json')
print()

# Find employees with foreign key dependencies
print("="*80)
print('CHECKING FOREIGN KEY DEPENDENCIES')
print("="*80)
print()

# Check which employees have records in other tables
tables_with_emp_refs = [
    ('driver_payroll', 'employee_id'),
    ('employee_expenses', 'employee_id'),
    ('driver_floats', 'driver_id'),
]

for table, col in tables_with_emp_refs:
    cur.execute(f'SELECT COUNT(DISTINCT {col}) FROM {table}')
    count = cur.fetchone()[0]
    print(f'{table:25s} | references {count} unique employees')

print()

# Find employees with NO dependencies (safe to delete if bogus)
cur.execute('''
    SELECT e.employee_id, e.full_name, e.employee_number
    FROM employees e
    LEFT JOIN driver_payroll dp ON e.employee_id = dp.employee_id
    LEFT JOIN employee_expenses ee ON e.employee_id = ee.employee_id
    WHERE dp.employee_id IS NULL AND ee.employee_id IS NULL
    ORDER BY e.employee_id
''')

orphans = cur.fetchall()
print(f'Employees with NO payroll/expense records: {len(orphans)}')
print('(Safe to delete if identified as bogus)')
print()

cur.close()
conn.close()

print("="*80)
print('NEXT STEPS')
print("="*80)
print('''
1. ✓ JSON backup created: employees_backup_before_migration.json
2. Identify which QBO_IMPORT / LEGACY_METADATA records to MERGE into REAL records
3. For duplicates (same name, multiple IDs):
   - Keep record with most non-NULL values
   - Merge remaining non-NULL fields into primary record
   - Update foreign keys (driver_payroll, employee_expenses) to point to primary ID
   - Delete duplicate records
4. Delete PLACEHOLDER records (Dead Employee File, Invoice Purposes, etc.)
5. Verify data integrity and referential constraints
6. Deploy changes incrementally with rollback capability
''')
