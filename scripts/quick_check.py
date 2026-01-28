import psycopg2, os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

print("Searching for KERI JENSEN:")
cur.execute("""
    SELECT client_id, client_name, account_number
    FROM clients
    WHERE LOWER(client_name) LIKE '%jensen%'
       OR LOWER(client_name) LIKE '%keri%'
""")
for row in cur.fetchall():
    print(f"  Client {row[0]}: {row[1]} (Account {row[2]})")

print("\nSearching for TANIA MACINNIS:")
cur.execute("""
    SELECT client_id, client_name, account_number
    FROM clients
    WHERE LOWER(client_name) LIKE '%macinnis%'
       OR LOWER(client_name) LIKE '%tania%'
""")
for row in cur.fetchall():
    print(f"  Client {row[0]}: {row[1]} (Account {row[2]})")

cur.close()
conn.close()
