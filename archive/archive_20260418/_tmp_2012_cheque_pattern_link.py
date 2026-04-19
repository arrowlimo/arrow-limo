import re
import csv
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

OUT=Path(r'l:\limo\data\audit')
OUT.mkdir(parents=True, exist_ok=True)
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')

cheque_num_re = re.compile(r'(?:CHQ|CHEQUE)\s*#?\s*(\d+)', re.IGNORECASE)

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

try:
    cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, description, vendor_extracted
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
      AND (
         COALESCE(description,'') ~* '(CHQ|CHEQUE)'
         OR COALESCE(vendor_extracted,'') ~* '(CHEQUE|CHQ)'
      )
    ORDER BY transaction_date, transaction_id
    """)
    txs=cur.fetchall()

    matches=[]
    for tx in txs:
        text=f"{tx['description'] or ''} {tx['vendor_extracted'] or ''}"
        nums=cheque_num_re.findall(text)
        cheque_num=nums[0] if nums else None

        if cheque_num:
            cur.execute("""
            SELECT receipt_id, receipt_date, gross_amount, vendor_name, description
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date)=2012
              AND banking_transaction_id IS NULL
              AND ABS(COALESCE(gross_amount,0)-%s) < 0.01
              AND receipt_date BETWEEN (%s::date - INTERVAL '5 day') AND (%s::date + INTERVAL '5 day')
              AND (
                COALESCE(description,'') ILIKE %s
                OR COALESCE(vendor_name,'') ILIKE %s
              )
            LIMIT 3
            """, (tx['debit_amount'], tx['transaction_date'], tx['transaction_date'], f"%{cheque_num}%", f"%{cheque_num}%"))
            cands=cur.fetchall()
        else:
            cur.execute("""
            SELECT receipt_id, receipt_date, gross_amount, vendor_name, description
            FROM receipts
            WHERE EXTRACT(YEAR FROM receipt_date)=2012
              AND banking_transaction_id IS NULL
              AND ABS(COALESCE(gross_amount,0)-%s) < 0.01
              AND receipt_date BETWEEN (%s::date - INTERVAL '2 day') AND (%s::date + INTERVAL '2 day')
            LIMIT 3
            """, (tx['debit_amount'], tx['transaction_date'], tx['transaction_date']))
            cands=cur.fetchall()

        if len(cands)==1:
            rid=cands[0]['receipt_id']
            matches.append({
                'transaction_id': tx['transaction_id'],
                'transaction_date': tx['transaction_date'],
                'debit_amount': float(tx['debit_amount']),
                'receipt_id': rid,
                'receipt_date': cands[0]['receipt_date'],
                'cheque_num': cheque_num or '',
                'description': tx['description'] or '',
            })

    for m in matches:
        cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s AND banking_transaction_id IS NULL", (m['transaction_id'], m['receipt_id']))
        cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s AND receipt_id IS NULL", (m['receipt_id'], m['transaction_id']))

    conn.commit()

    out_csv=OUT / f'2012_cheque_pattern_links_{stamp}.csv'
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['transaction_id','transaction_date','debit_amount','receipt_id','receipt_date','cheque_num','description'])
        w.writeheader(); w.writerows(matches)

    cur.execute("""
    SELECT COUNT(*) AS rows_no_receipt, COALESCE(SUM(debit_amount),0) AS amt_no_receipt
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
    """)
    rem=cur.fetchone()

    print('2012_cheque_pattern_links_applied:', len(matches))
    print('2012_cheque_pattern_csv:', out_csv)
    print('2012_unlinked_debits_remaining:', dict(rem))

except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
