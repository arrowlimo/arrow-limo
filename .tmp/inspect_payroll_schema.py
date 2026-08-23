from dotenv import load_dotenv
import os, psycopg2
load_dotenv('L:/limo/.env'); load_dotenv('L:/limo/.env.neon')
conn = psycopg2.connect(host=os.getenv('DB_HOST','localhost'), port=int(os.getenv('DB_PORT','5432')), dbname=os.getenv('DB_NAME','almsdata'), user=os.getenv('DB_USER','postgres'), password=os.getenv('DB_PASSWORD',''), sslmode=(os.getenv('DB_SSLMODE') or 'prefer'))
cur = conn.cursor()
for t in ['employees','employee_pay_master','pay_periods']:
    print('\n---', t, '---')
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (t,))
    print([r[0] for r in cur.fetchall()])
cur.close(); conn.close()
