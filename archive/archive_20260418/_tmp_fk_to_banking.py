import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT
    conrelid::regclass::text AS referencing_table,
    a.attname AS referencing_column,
    confrelid::regclass::text AS referenced_table
FROM pg_constraint c
JOIN pg_attribute a
  ON a.attrelid = c.conrelid
 AND a.attnum = ANY(c.conkey)
WHERE c.contype = 'f'
  AND c.confrelid = 'banking_transactions'::regclass
ORDER BY 1,2
""")
for r in cur.fetchall():
    print(dict(r))
cur.close(); conn.close()
