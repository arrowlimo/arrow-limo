#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find all tables with maint/service/repair/inspection
cur.execute("""
    SELECT table_name, 
           (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as cols
    FROM information_schema.tables t
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (table_name LIKE '%maint%' OR table_name LIKE '%service%' OR table_name LIKE '%repair%' OR table_name LIKE '%inspection%')
    ORDER BY table_name
""")

print('Tables with maintenance/service/repair/inspection:')
print(f"{'Table':<45} {'Columns':<10} {'Rows'}")
print('-'*70)

for table, cols in cur.fetchall():
    cur.execute(f'SELECT COUNT(*) FROM {table}')
    rows = cur.fetchone()[0]
    print(f'{table:<45} {cols:<10} {rows:>8,}')

cur.close()
conn.close()
