#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(host='localhost',port=5432,database='almsdata',user='postgres',password='ArrowLimousine')
cur = conn.cursor()
cur.execute("""
SELECT column_name, data_type, is_generated, generation_expression
FROM information_schema.columns
WHERE table_name='income_ledger'
ORDER BY ordinal_position
""")
for r in cur.fetchall():
    print(r)
cur.close()
conn.close()
