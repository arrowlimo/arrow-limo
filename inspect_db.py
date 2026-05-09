import psycopg2
try:
    conn = psycopg2.connect(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine')
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND (table_name ILIKE '%account%' OR table_name ILIKE '%gl%' OR table_name ILIKE '%ledger%') ORDER BY 1")
    print('TABLES')
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        print(t)
    print('---')
    
    check_tables = ['chart_of_accounts', 'accounts', 'account_codes', 'income_ledger', 'ledger_accounts', 'gl_accounts']
    for t in check_tables:
        cur.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=%s)", (t,))
        if cur.fetchone()[0]:
            print(f'FOUND {t}')
            cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='{t}' ORDER BY ordinal_position")
            cols = [c[0] for c in cur.fetchall()]
            print(f'COLS {cols}')
            try:
                cur.execute(f"SELECT * FROM {t} LIMIT 10")
                rows = cur.fetchall()
                print(f'ROWS {len(rows)}')
                for x in rows[:5]:
                    print(x)
            except Exception as e:
                print(f'ERR {e}')
                conn.rollback()
    conn.close()
except Exception as e:
    print(f'GLOBAL ERR {e}')
