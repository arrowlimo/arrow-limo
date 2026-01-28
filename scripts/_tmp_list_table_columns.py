import os
import sys
import psycopg2

table = sys.argv[1] if len(sys.argv) > 1 else 'banking_receipt_matching_ledger'

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()
cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
rows = cur.fetchall()
for c in rows:
    print(f"{c[0]} | {c[1]}")
cur.close(); conn.close()
