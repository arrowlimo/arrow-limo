import os
import psycopg2

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', 'ArrowLimousine'),
    port=int(os.getenv('DB_PORT', '5432')),
)
cur = conn.cursor()
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'employees'
      AND (column_name ILIKE '%rate%' OR column_name ILIKE '%hour%')
    ORDER BY ordinal_position
""")
for (name,) in cur.fetchall():
    print(name)
cur.close()
conn.close()
