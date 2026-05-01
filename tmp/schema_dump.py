import psycopg2
c = psycopg2.connect(host='localhost', port=5432, database='almsdata', user='postgres', password='ArrowLimousine')
cur = c.cursor()
for tbl in ('vehicles', 'clients', 'charters', 'employees', 'receipts', 'vendor_accounts', 'banking_transactions', 'charter_payments'):
    cur.execute(f"""
        SELECT column_name FROM information_schema.columns
        WHERE table_name='{tbl}' AND table_schema='public'
        ORDER BY ordinal_position
    """)
    print(f"\n{tbl}: {[r[0] for r in cur.fetchall()]}")
cur.close()
c.close()
