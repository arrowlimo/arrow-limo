import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name='employees' 
      AND (column_name LIKE '%license%' OR column_name LIKE '%permit%')
    ORDER BY column_name
""")
print("License/Permit columns:")
for r in cur.fetchall():
    print(f"  {r[0]}")
cur.close()
conn.close()
