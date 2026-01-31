import psycopg2

conn = psycopg2.connect('host=localhost dbname=almsdata user=postgres password=ArrowLimousine')
cur = conn.cursor()
cur.execute("""
    SELECT typname FROM pg_type WHERE typtype='e' ORDER BY typname
""")
print("Available ENUM types:")
for row in cur.fetchall():
    print(f"  - {row[0]}")
