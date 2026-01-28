import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)

cur = conn.cursor()

# Check charter_driver_pay
tables_to_check = [
    'charter_driver_pay',
    'invoices',
    'dispatch_events',
    'charter_incidents',
    'hos_log',
]

for table_name in tables_to_check:
    print(f'\n--- {table_name} ---')
    cur.execute(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = '{table_name}'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    if columns:
        print(f'Columns ({len(columns)}):')
        for col_name, col_type, nullable in columns:
            print(f'  {col_name:<30} {col_type:<20} {"NULL" if nullable=="YES" else "NOT NULL"}')
    else:
        print('TABLE NOT FOUND')

cur.close()
conn.close()
