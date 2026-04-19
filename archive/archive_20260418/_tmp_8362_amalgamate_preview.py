import psycopg2
from collections import defaultdict
conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

cur.execute("""
  SELECT
    bt8.transaction_id   AS bt8_id,
    bt1.transaction_id   AS bt1_id,
    bt8.transaction_date,
    COALESCE(bt8.debit_amount,0) AS debit,
    COALESCE(bt8.credit_amount,0) AS credit,
    bt8.description      AS desc_8362,
    bt1.description      AS desc_1615,
    bt8.category         AS cat_8362,
    bt1.category         AS cat_1615,
    bt8.reconciliation_status   AS status_8362,
    bt1.reconciliation_status   AS status_1615,
    bt8.reconciled_receipt_id   AS rec_rcpt_8362,
    bt1.reconciled_receipt_id   AS rec_rcpt_1615,
    bt8.is_transfer,
    bt8.reconciliation_notes    AS notes_8362,
    bt8.source_file      AS src_8362,
    bt1.source_file      AS src_1615,
    r8.receipt_id        AS linked_rcpt_id,
    r8.vendor_name       AS rcpt_vendor,
    r8.gl_code,
    r8.gl_description,
    r8.vehicle_number,
    r8.fuel,
    r8.fuel_amount,
    r8.description       AS rcpt_desc,
    r8.gross_amount      AS rcpt_gross,
    r8.is_paper_verified,
    rbl.linked_amount,
    rbl.link_status
  FROM banking_transactions bt8
  JOIN banking_transactions bt1
    ON bt1.account_number='1615'
    AND bt1.transaction_date = bt8.transaction_date
    AND COALESCE(bt1.debit_amount,0) = COALESCE(bt8.debit_amount,0)
    AND COALESCE(bt1.credit_amount,0) = COALESCE(bt8.credit_amount,0)
  JOIN receipt_banking_links rbl ON rbl.transaction_id = bt8.transaction_id
  JOIN receipts r8 ON r8.receipt_id = rbl.receipt_id
  WHERE bt8.account_number='0228362'
  AND bt8.transaction_date BETWEEN '2012-01-01' AND '2014-12-31'
  AND bt8.verified=TRUE
  ORDER BY bt8.transaction_date, bt8.transaction_id
""")
rows = cur.fetchall()
cols = [d[0] for d in cur.description]
print(f'Total pairs (with receipt links): {len(rows)}')
print()

# Categorise
case_a = []  # 1615 already reconciled too
case_b = []  # 1615 unreconciled → move receipt to 1615
for row in rows:
    d = dict(zip(cols, row))
    if d['rec_rcpt_1615'] is not None or d['status_1615'] == 'reconciled':
        case_a.append(d)
    else:
        case_b.append(d)

print(f'Case A (1615 already reconciled — review only): {len(case_a)}')
for d in case_a:
    print(f"  {d['transaction_date']}  debit={d['debit']:>8}  8362_rcpt={d['rec_rcpt_8362']}  1615_rcpt={d['rec_rcpt_1615']}  desc_1615={d['desc_1615']}")

print()
print(f'Case B (1615 unreconciled → amalgamate): {len(case_b)}')
for d in case_b:
    print(f"  {d['transaction_date']}  debit={d['debit']:>8}  credit={d['credit']:>8}  vendor={d['rcpt_vendor']}  gl={d['gl_code']}/{d['gl_description']}  veh={d['vehicle_number']}  fuel={d['fuel']}L/{d['fuel_amount']}  paper_verified={d['is_paper_verified']}")
    print(f"       bt8={d['bt8_id']} → bt1={d['bt1_id']}  linked_rcpt={d['linked_rcpt_id']}  link_status={d['link_status']}")

conn.close()
