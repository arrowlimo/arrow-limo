"""
Quick check of journal table schema.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print('JOURNAL TABLE COLUMNS:')
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'journal' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

print('\n' + '=' * 80)
print('UNIFIED_GENERAL_LEDGER TABLE COLUMNS:')
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'unified_general_ledger' 
    ORDER BY ordinal_position
""")
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

cur.close()
conn.close()
