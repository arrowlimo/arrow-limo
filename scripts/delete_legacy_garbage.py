import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=***REDACTED***')
cur = conn.cursor()

cur.execute("DELETE FROM employees WHERE employee_number LIKE 'LEGACY-%'")
count = cur.rowcount
conn.commit()

cur.execute("SELECT COUNT(*) FROM employees")
final = cur.fetchone()[0]

print(f"\n✅ Deleted {count} LEGACY garbage records")
print(f"Final employee count: {final}\n")

conn.close()
