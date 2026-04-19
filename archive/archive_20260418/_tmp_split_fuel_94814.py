"""
Investigate bt 94814 (split fuel 2012-09-24 $120) and its twin bt 140690.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Check both sides of the split
for bt_id in (94814, 140690):
    cur.execute("""
        SELECT transaction_id, transaction_date, debit_amount, credit_amount, description,
               account_number, reconciliation_status, is_transfer, business_personal
        FROM banking_transactions WHERE transaction_id=%s
    """, (bt_id,))
    r = cur.fetchone()
    if r:
        print(f"bt {r[0]}: date={r[1]} debit={r[2]} credit={r[3]} acct={r[5]} status={r[6]} is_transfer={r[7]}")
        print(f"  desc: {r[4]}")
    else:
        print(f"bt {bt_id}: NOT FOUND")

    # Check receipt_banking_links for this bt
    cur.execute("""
        SELECT rbl.link_id, rbl.receipt_id, rbl.linked_amount, rbl.link_status,
               r.receipt_date, r.gross_amount, r.vendor_name, r.description
        FROM receipt_banking_links rbl
        JOIN receipts r ON r.receipt_id = rbl.receipt_id
        WHERE rbl.transaction_id=%s
    """, (bt_id,))
    links = cur.fetchall()
    if links:
        for l in links:
            print(f"  -> receipt {l[1]} linked_amt={l[2]} status={l[3]} date={l[4]} vendor={l[6]} amt={l[5]} desc={str(l[7])[:50]}")
    else:
        print(f"  -> NO receipt_banking_links")
    print()

conn.close()
