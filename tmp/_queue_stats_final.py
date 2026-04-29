import psycopg
conn = psycopg.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine', sslmode='disable')
cur = conn.cursor()
cur.execute('''
SELECT
  COUNT(*) FILTER (WHERE processed_at IS NULL) AS pending,
  COUNT(*) FILTER (WHERE processed_at IS NOT NULL) AS processed,
  COUNT(*) FILTER (WHERE attempts >= 20 AND processed_at IS NULL) AS hard_failed
FROM sync.change_queue
''')
print(cur.fetchone())
cur.close()
conn.close()
