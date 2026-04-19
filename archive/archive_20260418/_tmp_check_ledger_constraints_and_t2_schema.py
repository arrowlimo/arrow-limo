#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='almsdata',
    user='postgres',
    password='ArrowLimousine'
)
cur = conn.cursor()

print('=== income_ledger constraints ===')
cur.execute("""
SELECT conname, pg_get_constraintdef(c.oid)
FROM pg_constraint c
WHERE conrelid = 'income_ledger'::regclass
ORDER BY conname;
""")
for row in cur.fetchall():
    print(row)

print('\n=== income_ledger indexes ===')
cur.execute("""
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename='income_ledger'
ORDER BY indexname;
""")
for row in cur.fetchall():
    print(row)

print('\n=== t2_deductibility_audit columns ===')
cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name='t2_deductibility_audit'
ORDER BY ordinal_position;
""")
for row in cur.fetchall():
    print(row)

print('\n=== t2_return_metadata columns ===')
cur.execute("""
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name='t2_return_metadata'
ORDER BY ordinal_position;
""")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
