"""List all backup tables."""
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_name LIKE '%backup%'
    ORDER BY table_name
""")

print("Backup tables found:")
for row in cur.fetchall():
    print(f"  {row[0]}")

conn.close()
