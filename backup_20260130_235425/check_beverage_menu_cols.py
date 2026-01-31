"""Check beverage_menu columns"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    dbname='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name='beverage_menu' 
    ORDER BY ordinal_position
""")

cols = cur.fetchall()

print('beverage_menu columns:\n')
for i, (col, dtype) in enumerate(cols, 1):
    print(f'{i:2d}. {col:20} ({dtype})')

cur.close()
conn.close()
