#!/usr/bin/env python
import psycopg2
import os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Check if table exists
cur.execute("SELECT EXISTS(SELECT FROM information_schema.tables WHERE table_name = 'vehicle_pricing_defaults')")
exists = cur.fetchone()[0]
print(f'Table exists: {exists}')

if exists:
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'vehicle_pricing_defaults' ORDER BY ordinal_position")
    print('Current columns:')
    for col, dtype in cur.fetchall():
        print(f'  {col}: {dtype}')
else:
    print('Table does not exist - will create it')

conn.close()
