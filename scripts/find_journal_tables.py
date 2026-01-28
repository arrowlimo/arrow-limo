#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

# Find tables with journal/entry/ledger
cur.execute("""
    SELECT table_name, 
           (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as cols
    FROM information_schema.tables t
    WHERE table_schema = 'public'
    AND table_type = 'BASE TABLE'
    AND (table_name LIKE '%journal%' OR table_name LIKE '%entry%' OR table_name LIKE '%ledger%')
    ORDER BY table_name
""")

print('Tables with journal/entry/ledger:')
print(f"{'Table':<50} {'Columns':<10} {'Rows'}")
print('-'*75)

for table, cols in cur.fetchall():
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        rows = cur.fetchone()[0]
        print(f'{table:<50} {cols:<10} {rows:>8,}')
    except Exception as e:
        print(f'{table:<50} {cols:<10} ERROR: {e}')

cur.close()
conn.close()
