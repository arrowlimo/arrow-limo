import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REMOVED***')
cur = conn.cursor()

names_to_inactivate = [
    'Fajardo, Junifer Jose',
    'Peacock, Barbara',
    'Liberty, Ongpico'
]

print('\nMarking specific drivers as inactive...')
cur.execute("""
    UPDATE employees
    SET status = 'inactive'
    WHERE full_name = ANY(%s)
""", (names_to_inactivate,))

conn.commit()
print(f"Updated {cur.rowcount} records to inactive.")

# Show active count
cur.execute("""
    SELECT COUNT(*) FROM employees WHERE is_chauffeur = TRUE AND status = 'active'
""")
active = cur.fetchone()[0]
print(f"Active drivers now: {active}\n")

conn.close()
