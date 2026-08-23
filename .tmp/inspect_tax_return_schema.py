import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('L:/limo/.env')
conn = psycopg2.connect(
    host=os.getenv('LOCAL_DB_HOST', 'localhost'),
    dbname=os.getenv('LOCAL_DB_NAME', 'almsdata'),
    user=os.getenv('LOCAL_DB_USER', 'postgres'),
    password=os.getenv('LOCAL_DB_PASSWORD', ''),
    port=os.getenv('LOCAL_DB_PORT', '5432'),
    sslmode='disable',
)
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name")
all_tables = [r[0] for r in cur.fetchall()]
for name in all_tables:
    if 'tax' in name.lower() or 'return' in name.lower() or 't1' in name.lower() or 't4' in name.lower():
        print(name)
        cur.execute("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (name,))
        for row in cur.fetchall():
            print(' ', row)
        print()
cur.close(); conn.close()
