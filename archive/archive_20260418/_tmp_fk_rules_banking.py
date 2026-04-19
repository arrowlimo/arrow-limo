import psycopg2
from psycopg2.extras import RealDictCursor
conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT
  tc.table_name AS referencing_table,
  kcu.column_name AS referencing_column,
  ccu.table_name AS referenced_table,
  ccu.column_name AS referenced_column,
  rc.update_rule,
  rc.delete_rule,
  cols.is_nullable,
  cols.data_type
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints rc
  ON rc.constraint_name = tc.constraint_name
 AND rc.constraint_schema = tc.table_schema
JOIN information_schema.columns cols
  ON cols.table_schema = tc.table_schema
 AND cols.table_name = kcu.table_name
 AND cols.column_name = kcu.column_name
WHERE tc.constraint_type='FOREIGN KEY'
  AND ccu.table_name='banking_transactions'
  AND ccu.column_name='transaction_id'
ORDER BY tc.table_name, kcu.column_name
""")
for r in cur.fetchall():
    print(dict(r))
cur.close(); conn.close()
