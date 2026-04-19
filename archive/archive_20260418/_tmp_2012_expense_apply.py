import csv
from pathlib import Path
from decimal import Decimal
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

OUT=Path(r'l:\limo\data\audit')
OUT.mkdir(parents=True, exist_ok=True)
stamp=datetime.now().strftime('%Y%m%d_%H%M%S')

FEE_MAP=[
    (r'NSF\s*FEE|NON-?SUFFICIENT', '5715', 'NSF Fees', 'NSF FEE'),
    (r'MERCH|MERCHANT\s+SERVICES|GBL\s+MERCH', '5720', 'Credit Card Processing Fees', 'MERCHANT FEE'),
    (r'BANK\s+FEE|BANK\s+CHARGES|SERVICE\s+CHARGE|ACCOUNT\s+FEE|OVERDRAFT|INTEREST\b', '5710', 'Bank Fees', 'BANK FEE'),
]

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

try:
    # Pass 1: strict unique existing receipt matching (same date+amount)
    cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, description, vendor_extracted
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
    ORDER BY transaction_date, transaction_id
    """)
    txs=cur.fetchall()

    strict_links=[]
    for tx in txs:
        cur.execute("""
        SELECT receipt_id
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date)=2012
          AND banking_transaction_id IS NULL
          AND COALESCE(gross_amount,0)>0
          AND receipt_date=%s
          AND ABS(COALESCE(gross_amount,0)-%s)<0.01
        LIMIT 3
        """, (tx['transaction_date'], tx['debit_amount']))
        cands=cur.fetchall()
        if len(cands)==1:
            rid=cands[0]['receipt_id']
            strict_links.append((tx['transaction_id'], rid, tx['transaction_date'], float(tx['debit_amount']), tx['description']))

    for tx_id, rid, *_ in strict_links:
        cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s AND banking_transaction_id IS NULL", (tx_id, rid))
        cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s AND receipt_id IS NULL", (rid, tx_id))

    # Pass 2: create receipts for clear fee debits still unlinked
    cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, description, vendor_extracted
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
    ORDER BY transaction_date, transaction_id
    """)
    rem=cur.fetchall()

    created=[]
    for tx in rem:
        desc=(tx['description'] or '').strip()
        vendor=(tx['vendor_extracted'] or '').strip()
        gl=None; category=None; vendor_name=None
        for pat, gl_code, cat, default_vendor in FEE_MAP:
            import re
            if re.search(pat, f"{desc} {vendor}", re.IGNORECASE):
                gl=gl_code; category=cat; vendor_name=default_vendor
                break
        if not gl:
            continue

        cur.execute("""
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount, gst_amount,
            category, gl_account_code, banking_transaction_id, created_from_banking,
            receipt_source, created_at, updated_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s,NOW(),NOW())
        RETURNING receipt_id
        """, (
            tx['transaction_date'], vendor_name, desc, tx['debit_amount'], Decimal('0.00'),
            category, gl, tx['transaction_id'], 'auto_2012_fee_backfill'
        ))
        rid=cur.fetchone()['receipt_id']
        cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s AND receipt_id IS NULL", (rid, tx['transaction_id']))
        created.append((tx['transaction_id'], rid, tx['transaction_date'], float(tx['debit_amount']), desc, gl, category))

    conn.commit()

    strict_csv=OUT/f'2012_strict_links_{stamp}.csv'
    with strict_csv.open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['transaction_id','receipt_id','transaction_date','amount','description'])
        for r in strict_links:
            w.writerow(r)

    created_csv=OUT/f'2012_fee_receipts_created_{stamp}.csv'
    with created_csv.open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f)
        w.writerow(['transaction_id','receipt_id','transaction_date','amount','description','gl_account_code','category'])
        for r in created:
            w.writerow(r)

    print('2012_STRICT_LINKS_APPLIED:', len(strict_links))
    print('2012_FEE_RECEIPTS_CREATED:', len(created))
    print('STRICT_LINKS_CSV:', strict_csv)
    print('FEE_CREATED_CSV:', created_csv)

except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
