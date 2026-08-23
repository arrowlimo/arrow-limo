from dotenv import load_dotenv
import os, psycopg2
load_dotenv('L:/limo/.env'); load_dotenv('L:/limo/.env.neon')
conn = psycopg2.connect(host=os.getenv('DB_HOST','localhost'), port=int(os.getenv('DB_PORT','5432')), dbname=os.getenv('DB_NAME','almsdata'), user=os.getenv('DB_USER','postgres'), password=os.getenv('DB_PASSWORD',''), sslmode=(os.getenv('DB_SSLMODE') or 'prefer'))
cur = conn.cursor()
cur.execute("""
SELECT employee_id, COALESCE(full_name,name,''), COALESCE(employee_number,''), COALESCE(salary_deferred,0)
FROM employees
WHERE COALESCE(salary_deferred,0) > 0
   OR LOWER(COALESCE(full_name,'')) LIKE '%owner%'
   OR LOWER(COALESCE(full_name,'')) LIKE '%patrick%'
   OR LOWER(COALESCE(name,'')) LIKE '%patrick%'
ORDER BY employee_id
""")
for r in cur.fetchall():
    print(r)
cur.close(); conn.close()
