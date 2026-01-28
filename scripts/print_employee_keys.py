import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST','localhost'),
        database=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***')
    )

conn = get_db_connection()
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute("SELECT employee_id, employee_number, full_name FROM employees ORDER BY employee_id LIMIT 50")
rows = cur.fetchall()
print(f"employees rows: {len(rows)} (first 50)")
for r in rows:
    print(r['employee_id'], r['employee_number'], r['full_name'])
cur.close(); conn.close()
