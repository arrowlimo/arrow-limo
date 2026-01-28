import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

# Get all columns
cur.execute('''
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'employees'
ORDER BY ordinal_position
''')

cols = cur.fetchall()
print(f'Total columns in employees: {len(cols)}\n')
print('='*80)

# Check which columns are 100% NULL
empty_cols = []
sparse_cols = []
used_cols = []

print('Column Usage Analysis:\n')
for col_name, data_type, nullable in cols:
    cur.execute(f'SELECT COUNT(*) FROM employees WHERE "{col_name}" IS NOT NULL')
    non_null = cur.fetchone()[0]
    
    if non_null == 0:
        empty_cols.append((col_name, data_type))
        print(f'  ❌ {col_name:35s} | {data_type:20s} | 0 of 1003 (COMPLETELY EMPTY!)')
    elif non_null < 10:
        sparse_cols.append((col_name, data_type, non_null))
        print(f'  ⚠️  {col_name:35s} | {data_type:20s} | {non_null:3d} of 1003 (sparse)')
    else:
        used_cols.append((col_name, data_type, non_null))
        print(f'  ✓  {col_name:35s} | {data_type:20s} | {non_null:4d} of 1003')

print('\n' + '='*80)
print(f'\nSUMMARY:')
print(f'  ✓  Used columns:    {len(used_cols)}')
print(f'  ⚠️  Sparse columns:  {len(sparse_cols)}')
print(f'  ❌ Empty columns:   {len(empty_cols)}')
print(f'\nTOTAL: {len(cols)} columns (should be much fewer!)')

print(f'\n\nCOLUMNS THAT CAN BE DELETED (completely empty):')
for col_name, data_type in empty_cols:
    print(f'  - {col_name} ({data_type})')

print(f'\n\nCOLUMNS THAT ARE BARELY USED (sparse):')
for col_name, data_type, count in sparse_cols:
    print(f'  - {col_name} ({count} values out of 1003)')
