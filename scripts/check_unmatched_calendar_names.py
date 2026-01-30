#!/usr/bin/env python3
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

names = ['dave', 'david', 'shaylene', 'barb', 'barbara', 'madeline', 
         'allana', 'alana', 'shondel', 'tabitha', 'tabatha', 'sam', 
         'samuel', 'samantha', 'gerry', 'gerald', 'ron', 'ronald']

cur.execute("""
    SELECT employee_id, first_name, last_name, full_name 
    FROM employees 
    WHERE is_chauffeur = true 
    AND (LOWER(first_name) = ANY(%s) 
         OR LOWER(last_name) = ANY(%s)
         OR full_name ~* %s)
    ORDER BY first_name, last_name
""", (names, names, '(' + '|'.join(names) + ')'))

rows = cur.fetchall()
print('Chauffeurs matching unmatched calendar names:')
print('=' * 60)
for r in rows:
    print(f'  ID {r[0]:>3}: {r[1]} {r[2]} ({r[3]})')

cur.close()
conn.close()
