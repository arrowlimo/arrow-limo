from dotenv import load_dotenv
import os, psycopg2

load_dotenv('L:/limo/.env')
load_dotenv('L:/limo/.env.neon')
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    port=int(os.getenv('DB_PORT', '5432')),
    dbname=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', ''),
    sslmode=(os.getenv('DB_SSLMODE') or 'prefer'),
)
cur = conn.cursor()
cur.execute("""
SELECT year,
       cpp_contribution_rate_employee,
       cpp_max_employee_contribution,
       cpp_max_pensionable_earnings,
       cpp_basic_exemption,
       ei_rate,
       ei_max_employee_contribution,
       ei_max_insurable_earnings
FROM tax_year_reference
WHERE year BETWEEN 2012 AND 2026
ORDER BY year
""")
for r in cur.fetchall():
    print(r)
cur.close(); conn.close()
