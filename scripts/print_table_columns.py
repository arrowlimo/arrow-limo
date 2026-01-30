import psycopg2

def print_columns(table):
    conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position
        """,
        (table,)
    )
    cols = [r[0] for r in cur.fetchall()]
    print(f"\n{table.upper()} COLUMNS:\n" + ", ".join(cols))
    cur.close(); conn.close()

if __name__ == '__main__':
    for t in ['vehicles','employees','receipts','clients','charters','driver_payroll','payments','users']:
        print_columns(t)
