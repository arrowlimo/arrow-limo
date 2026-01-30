import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
cur = conn.cursor()
cur.execute("SELECT employee_id, employee_number, full_name FROM employees WHERE full_name ILIKE '%paul%' ORDER BY employee_id")
print("Employees with 'Paul' in name:")
for r in cur.fetchall():
    print(f"ID: {r[0]}, Number: [{r[1]}], Name: {r[2]}")
cur.close()
conn.close()
