import psycopg2, os
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()
cur.execute("""
    SELECT column_name, is_nullable, column_default, data_type 
    FROM information_schema.columns 
    WHERE table_name='payments' 
    ORDER BY ordinal_position
""")
for col, nullable, default, dtype in cur.fetchall():
    print(f'{col:30s} | {dtype:15s} | NULL:{nullable:1s} | DEF:{str(default)[:25]:25s}')
cur.close()
conn.close()
