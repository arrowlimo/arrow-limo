"""
Compare bt 94814 and bt 69364 - are they the same physical transaction?
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

for bt_id in (94814, 94813, 69364):
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount,
               description, account_number, reconciliation_status, is_transfer,
               source_file, import_batch, transaction_uid, transaction_hash
        FROM banking_transactions WHERE transaction_id=%s
    """, (bt_id,))
    r = cur.fetchone()
    if r:
        print(f"bt {r[0]}: acct={r[5]} date={r[1]} debit={r[2]} status={r[6]} source={r[8]}")
        print(f"  desc: {r[4]}")
        print(f"  uid={r[10]}  hash={r[11]}")
    else:
        print(f"bt {bt_id}: NOT FOUND")
    
    cur.execute("""
        SELECT rbl.receipt_id, rbl.linked_amount, r.gross_amount, r.vendor_name, r.description
        FROM receipt_banking_links rbl
        JOIN receipts r ON r.receipt_id = rbl.receipt_id
        WHERE rbl.transaction_id=%s
    """, (bt_id,))
    links = cur.fetchall()
    for l in links:
        print(f"  -> receipt {l[0]} linked={l[1]} gross={l[2]} vendor={l[3]} desc={str(l[4])[:50]}")
    print()

conn.close()
