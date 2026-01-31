import psycopg2, os
DB_HOST=os.environ.get('DB_HOST','localhost')
conn=psycopg2.connect(host=DB_HOST, database='almsdata', user='postgres', password='ArrowLimousine')
cur=conn.cursor()
cur.execute("""
    SELECT account_code, account_name
    FROM chart_of_accounts
    WHERE account_name ILIKE '%registration%' OR account_name ILIKE '%license%'
    ORDER BY account_code
""")
for code,name in cur.fetchall():
    print(f"{code}\t{name}")
cur.close()
conn.close()
