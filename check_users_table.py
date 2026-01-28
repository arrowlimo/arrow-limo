import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Check if users table exists
cur.execute('''
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'users'
    ORDER BY ordinal_position
''')

cols = cur.fetchall()
if cols:
    print('Users table structure:')
    for col_name, data_type, nullable in cols:
        nullable_str = 'NULL' if nullable == 'YES' else 'NOT NULL'
        print(f'  {col_name:<20} {data_type:<15} {nullable_str}')
else:
    print('No users table found. Checking employees table...')
    cur.execute('''
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'employees'
        ORDER BY ordinal_position
    ''')
    cols = cur.fetchall()
    if cols:
        print('Employees table structure:')
        for col_name, data_type, nullable in cols:
            nullable_str = 'NULL' if nullable == 'YES' else 'NOT NULL'
            print(f'  {col_name:<20} {data_type:<15} {nullable_str}')

cur.close()
conn.close()
