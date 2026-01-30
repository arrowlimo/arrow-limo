import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

# Mark Joe Smith as inactive (test driver)
cur.execute("""
    UPDATE employees
    SET status = 'inactive'
    WHERE full_name = 'Smith, Joe'
""")

conn.commit()

# Verify
cur.execute("""
    SELECT employee_id, employee_number, full_name, status, is_chauffeur
    FROM employees
    WHERE full_name = 'Smith, Joe'
""")

result = cur.fetchone()

print(f"\n✅ Marked Joe Smith as inactive (test driver for database)\n")
print(f"ID: {result[0]}")
print(f"Employee Number: {result[1]}")
print(f"Full Name: {result[2]}")
print(f"Status: {result[3]}")
print(f"Is Chauffeur: {result[4]}\n")

conn.close()
