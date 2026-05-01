import psycopg2
c = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = c.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='banking_transactions' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print('COLS:', cols)
# Also check deposit_slip_items
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='deposit_slip_items' ORDER BY ordinal_position")
dsi_cols = [r[0] for r in cur.fetchall()]
print('DSI_COLS:', dsi_cols)
