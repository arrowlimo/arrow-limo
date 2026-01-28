#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Get banking_transactions columns
cur.execute('''
    SELECT column_name, data_type, column_default, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
''')

print('BANKING_TRANSACTIONS TABLE STRUCTURE:')
print('='*100)
print(f'{"Column Name":30} | {"Data Type":20} | {"Default":25} | {"Nullable":10}')
print('-'*100)
for col_name, data_type, default, nullable in cur.fetchall():
    default_str = str(default) if default else 'NULL'
    print(f'{col_name:30} | {data_type:20} | {default_str:25} | {nullable:10}')

print()

# Check for primary key
cur.execute('''
    SELECT column_name
    FROM information_schema.constraint_column_usage
    WHERE table_name = 'banking_transactions'
    AND constraint_name IN (
        SELECT constraint_name FROM information_schema.table_constraints
        WHERE table_name = 'banking_transactions' AND constraint_type = 'PRIMARY KEY'
    )
''')
pk = cur.fetchall()
print(f'Primary Key Column: {pk[0][0] if pk else "None"}')
print()

# Sample data
cur.execute('SELECT * FROM banking_transactions LIMIT 1')
cols = [desc[0] for desc in cur.description]
data = cur.fetchone()

print('Sample Row Data:')
print('-'*100)
if data:
    for col_name, val in zip(cols, data):
        print(f'  {col_name:30} : {str(val)[:60]}')

print()

# Count records
cur.execute('SELECT COUNT(*) FROM banking_transactions')
count = cur.fetchone()[0]
print(f'Total records: {count:,}')

cur.close()
conn.close()
