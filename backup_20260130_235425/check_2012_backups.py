import psycopg2, os
conn = psycopg2.connect(host=os.getenv('DB_HOST', 'localhost'), database=os.getenv('DB_NAME', 'almsdata'), user=os.getenv('DB_USER', 'postgres'), password=os.getenv('DB_PASSWORD', '***REDACTED***'))
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'banking_transactions_2012_backup%' ORDER BY table_name")
for r in cur.fetchall():
    print(r[0])
