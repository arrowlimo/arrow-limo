import os, sys
sys.path.insert(0, 'desktop_app')
import psycopg2

conn = psycopg2.connect(
    host=os.getenv("DB_HOST", "ep-curly-dream-afnuyxfx-pooler.c-2.us-west-2.aws.neon.tech"),
    port=int(os.getenv("DB_PORT", "5432")),
    dbname=os.getenv("DB_NAME", "neondb"),
    user=os.getenv("DB_USER", "neondb_owner"),
    password=os.getenv("DB_PASSWORD", ""),
    sslmode="require"
)
cur = conn.cursor()
cur.execute("""
    SELECT conname, contype, pg_get_constraintdef(oid) 
    FROM pg_constraint 
    WHERE conrelid = 'beverage_products'::regclass
""")
print("beverage_products constraints:")
for r in cur.fetchall():
    print(" ", r)
cur.execute("""
    SELECT column_name, is_nullable, column_default 
    FROM information_schema.columns 
    WHERE table_schema='public' AND table_name='clients' 
    ORDER BY ordinal_position
""")
print("\nclients columns:")
for r in cur.fetchall():
    print(" ", r)
cur.execute("""
    SELECT conname, contype, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conrelid = 'charter_payments'::regclass
""")
print("\ncharter_payments constraints:")
for r in cur.fetchall():
    print(" ", r)
conn.close()
