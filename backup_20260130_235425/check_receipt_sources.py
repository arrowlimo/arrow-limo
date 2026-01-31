import psycopg2
c = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = c.cursor()
cur.execute("SELECT COUNT(*) FROM receipts WHERE source_system LIKE '%Scotia%' OR source_system LIKE '%903990%'")
print(f'Scotia receipts: {cur.fetchone()[0]}')
cur.execute("SELECT COUNT(*) FROM receipts WHERE source_system LIKE '%2012%'")
print(f'2012 receipts: {cur.fetchone()[0]}')
cur.execute("SELECT DISTINCT source_system FROM receipts WHERE source_system LIKE '%Banking%' ORDER BY source_system")
print('\nBanking source systems:')
for row in cur.fetchall():
    cur2 = c.cursor()
    cur2.execute("SELECT COUNT(*) FROM receipts WHERE source_system = %s", (row[0],))
    count = cur2.fetchone()[0]
    print(f'  {row[0]}: {count} receipts')
c.close()
