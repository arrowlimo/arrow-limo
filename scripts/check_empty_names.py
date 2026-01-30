import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT employee_id, employee_number, full_name FROM employees WHERE employee_number IN ('Dr114', 'Dr128', 'DR114', 'DR128') ORDER BY employee_id")
for r in cur.fetchall():
    print(f"ID: {r[0]}, Number: {r[1]}, Name: [{r[2]}]")
cur.close()
conn.close()
