import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
try:
    cur.execute("SELECT COUNT(*) FROM employees WHERE is_active = true")
    count = cur.fetchone()[0]
    print(f"✅ Employees table exists. Active: {count}")
except Exception as e:
    print(f"❌ Error: {e}")
finally:
    cur.close()
    conn.close()
