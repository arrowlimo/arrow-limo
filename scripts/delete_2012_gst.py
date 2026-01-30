import psycopg2

conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("DELETE FROM charter_gst_details_2010_2012 WHERE source_sheet = '2012 CS'")
conn.commit()
print(f'✓ Deleted {cur.rowcount} 2012 records')
cur.close()
conn.close()
