import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

# strict candidate set: debit tx with no receipt link and non-transfer descriptions
cur.execute("""
SELECT bt.transaction_id, bt.transaction_date, bt.debit_amount, bt.description
FROM banking_transactions bt
WHERE COALESCE(bt.debit_amount,0) > 0
  AND bt.receipt_id IS NULL
  AND COALESCE(bt.description,'') !~* '(transfer|e-?transfer|interac\\s*e-?transfer|payment\\s+received|deposit|interest|nsf\\s*reversal|reversal|refund|cheque\\s+deposit|mobile\\s+deposit|from\\s+account|to\\s+account|cash withdrawal|atm withdrawal|owner draw)'
ORDER BY bt.transaction_date, bt.transaction_id
""")
rows=cur.fetchall()

matches=[]
for r in rows:
    cur.execute("""
    SELECT r.receipt_id
    FROM receipts r
    WHERE r.banking_transaction_id IS NULL
      AND COALESCE(r.gross_amount,0)>0
      AND r.receipt_date = %s
      AND ABS(COALESCE(r.gross_amount,0) - %s) < 0.01
    LIMIT 3
    """, (r['transaction_date'], r['debit_amount']))
    cands=cur.fetchall()
    if len(cands)==1:
        matches.append((r['transaction_id'], cands[0]['receipt_id']))

print('strict_unique_date_amount_matches:', len(matches))

# apply
for tx_id, receipt_id in matches:
    cur.execute("""
    UPDATE receipts SET banking_transaction_id=%s
    WHERE receipt_id=%s AND banking_transaction_id IS NULL
    """, (tx_id, receipt_id))
    cur.execute("""
    UPDATE banking_transactions SET receipt_id=%s
    WHERE transaction_id=%s AND receipt_id IS NULL
    """, (receipt_id, tx_id))

conn.commit()
print('applied_links:', len(matches))

cur.execute("""SELECT COUNT(*) FROM banking_transactions WHERE COALESCE(debit_amount,0)>0 AND receipt_id IS NULL""")
print('remaining_unlinked_debits_rows:', cur.fetchone()['count'])

cur.close(); conn.close()
