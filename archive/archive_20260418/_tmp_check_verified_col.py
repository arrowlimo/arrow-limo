import psycopg2
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata',
                        user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='banking_transactions' ORDER BY column_name")
cols = [r[0] for r in cur.fetchall()]
keywords = ['verif','paper','manual','review','confirm','audit','flag','note']
matched = [c for c in cols if any(w in c for w in keywords)]
print("Matched:", matched)
print("All cols:", cols)

# Also check those 13 specific transaction_ids
ids = [100347,100348,100373,100376,100378,100377,100379,100380,100381,88934,100382,100384,100385]
cur.execute("SELECT transaction_id, " + ", ".join(matched) + " FROM banking_transactions WHERE transaction_id = ANY(%s)", (ids,)) if matched else None
if matched:
    for r in cur.fetchall():
        print(r)
conn.close()
