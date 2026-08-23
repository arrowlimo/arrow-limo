from dotenv import load_dotenv
import os
import psycopg2

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
for t in ['tax_year_reference','federal_tax_brackets','alberta_tax_brackets','corporate_tax_rates','wcb_ab_premium_rates','wcb_ab_industry_rates']:
    print(f'--- {t} ---')
    cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name=%s
    ORDER BY ordinal_position
    """, (t,))
    cols = cur.fetchall()
    if not cols:
        print('missing')
        continue
    print('cols:', ', '.join(c for c,_ in cols))
    year_cols = [c for c,_ in cols if c in ('year','tax_year','fiscal_year')]
    if year_cols:
        yc = year_cols[0]
        cur.execute(f"SELECT MIN({yc}), MAX({yc}), COUNT(DISTINCT {yc}) FROM {t}")
        print('range/count:', cur.fetchone())
        cur.execute(f"SELECT {yc}, COUNT(*) FROM {t} WHERE {yc} BETWEEN 2012 AND 2026 GROUP BY {yc} ORDER BY {yc}")
        rows = cur.fetchall()
        print('years:', rows)
    else:
        print('no year column')
print('--- done ---')
cur.close(); conn.close()
