import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

search_terms = ['RICHARD', 'PAUL', 'DAVID', 'BARB', 'PEACOCK', 'BRITTANY', 'JEANNIE', 'SHILLINGTON', 'MATTHEW', 'MORRIS', 'SHERRI', 'MICHAEL']

cur.execute("SELECT employee_id, first_name, last_name FROM employees WHERE last_name IS NOT NULL ORDER BY last_name, first_name")
results = []
for emp_id, fname, lname in cur.fetchall():
    full = f'{fname} {lname}'.upper()
    for term in search_terms:
        if term in full:
            results.append((emp_id, fname, lname))
            break

print("FOUND MATCHES:")
for emp_id, fname, lname in sorted(results):
    print(f'{emp_id:6d} | {fname:20s} {lname}')

cur.close()
conn.close()
