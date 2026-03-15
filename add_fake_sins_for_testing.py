#!/usr/bin/env python3
"""
Add fake SIN numbers for testing T4 generation
"""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="ArrowLimousine"
)

cur = conn.cursor()

# Add fake SINs for the 3 employees
updates = [
    (1979, '999888777', 'DEANS, Gordon'),
    (45, '888777666', 'Derksen, Daryl'),
    (44, '777666555', 'Flinn, Winston')
]

print("Adding fake SIN numbers for testing...")
print()

for emp_id, fake_sin, name in updates:
    cur.execute("""
        UPDATE employees 
        SET t4_sin = %s 
        WHERE employee_id = %s
    """, (fake_sin, emp_id))
    
    print(f"✓ Updated {name} (ID: {emp_id}) - SIN: {fake_sin}")

conn.commit()
print()
print(f"Updated {len(updates)} employee records")

cur.close()
conn.close()
