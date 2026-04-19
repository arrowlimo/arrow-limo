import csv
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

out_dir=Path(r'l:\limo\data\audit')
out_dir.mkdir(parents=True, exist_ok=True)
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

try:
    cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, description
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
      AND COALESCE(description,'') ~* 'CASH WITHDRAWAL|ATM WITHDRAWAL'
    ORDER BY transaction_date, transaction_id
    """)
    rows=cur.fetchall()

    created=[]
    for tx in rows:
        cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount, gst_amount,
            category, gl_account_code, banking_transaction_id,
            created_from_banking, receipt_source,
            exclude_from_reports, is_personal_purchase, owner_personal_amount,
            created_at, updated_at
        ) VALUES (%s,%s,%s,%s,0,%s,%s,%s,TRUE,%s,TRUE,TRUE,%s,NOW(),NOW())
        RETURNING receipt_id
        """, (
            tx['transaction_date'],
            'OWNER WITHDRAWAL',
            tx['description'] or 'Cash withdrawal',
            tx['debit_amount'],
            'Owner Withdrawal',
            '3020',
            tx['transaction_id'],
            'auto_2012_cash_withdrawal_backfill',
            tx['debit_amount'],
        ))
        rid=cur.fetchone()['receipt_id']
        cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s AND receipt_id IS NULL", (rid, tx['transaction_id']))
        created.append((tx['transaction_id'], rid, tx['transaction_date'], float(tx['debit_amount']), tx['description']))

    conn.commit()

    out_csv=out_dir / f'2012_cash_withdrawal_backfill_{stamp}.csv'
    with out_csv.open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['transaction_id','receipt_id','transaction_date','amount','description'])
        for r in created:
            w.writerow(r)

    cur.execute("""
    SELECT COUNT(*) AS rows_no_receipt, COALESCE(SUM(debit_amount),0) AS amt_no_receipt
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
    """)
    rem=cur.fetchone()

    print('2012_cash_withdrawal_receipts_created:', len(created))
    print('2012_cash_withdrawal_csv:', out_csv)
    print('2012_unlinked_debits_remaining:', dict(rem))

except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
