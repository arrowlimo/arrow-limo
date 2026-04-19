import re
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
    SELECT transaction_id, transaction_date, debit_amount, description, vendor_extracted
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
      AND (
        COALESCE(vendor_extracted,'') ILIKE '%%HEFFNER%%'
        OR COALESCE(description,'') ILIKE '%%HEFFNER%%'
      )
    ORDER BY transaction_date, transaction_id
    """)
    heffner_txs=cur.fetchall()

    heffner_links=[]
    for tx in heffner_txs:
        cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, vendor_name, description
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date)=2012
          AND banking_transaction_id IS NULL
          AND ABS(COALESCE(gross_amount,0)-%s)<0.01
          AND receipt_date BETWEEN (%s::date - INTERVAL '5 day') AND (%s::date + INTERVAL '5 day')
          AND (
            COALESCE(vendor_name,'') ILIKE '%%HEFFNER%%'
            OR COALESCE(description,'') ILIKE '%%HEFFNER%%'
            OR COALESCE(vendor_name,'') ILIKE '%%LEXUS%%'
            OR COALESCE(description,'') ILIKE '%%LEXUS%%'
          )
        LIMIT 3
        """, (tx['debit_amount'], tx['transaction_date'], tx['transaction_date']))
        cands=cur.fetchall()
        if len(cands)==1:
            rid=cands[0]['receipt_id']
            heffner_links.append({
                'transaction_id': tx['transaction_id'],
                'transaction_date': tx['transaction_date'],
                'amount': float(tx['debit_amount']),
                'receipt_id': rid,
                'receipt_date': cands[0]['receipt_date'],
                'description': tx['description'] or '',
            })

    for m in heffner_links:
        cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s AND banking_transaction_id IS NULL", (m['transaction_id'], m['receipt_id']))
        cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s AND receipt_id IS NULL", (m['receipt_id'], m['transaction_id']))

    stopwords = {
        'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','SERVICE','CHARGE',
        'FULL','SELF','OVERDRAFT','INTEREST','ELECTRONIC','FUNDS','TRANSFER','NETWORK','FEE',
        'ATM','CANADA','GAB','PAYMENT','DEBIT','CREDIT','CHEQUE','WITHDRAWAL','MOBILE','DEPOSIT'
    }
    token_pat = re.compile(r"[A-Z][A-Z'&.-]{2,}")
    exclude_pat = re.compile(r"(transfer|e-?transfer|payment\s+received|deposit|refund|reversal|nsf\s*reversal|cash withdrawal|atm withdrawal|owner draw)", re.IGNORECASE)

    cur.execute("""
    SELECT transaction_id, transaction_date, debit_amount, description
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
      AND (vendor_extracted IS NULL OR vendor_extracted='')
    ORDER BY transaction_date, transaction_id
    """)
    blank_txs=cur.fetchall()

    token_links=[]
    for tx in blank_txs:
        desc = tx['description'] or ''
        if exclude_pat.search(desc):
            continue

        raw_tokens = token_pat.findall(desc.upper())
        tokens=[]
        seen=set()
        for t in raw_tokens:
            if t in stopwords or t.isdigit() or len(t)<3:
                continue
            if t not in seen:
                seen.add(t)
                tokens.append(t)
        tokens=tokens[:3]
        if not tokens:
            continue

        cur.execute("""
        SELECT receipt_id, vendor_name, description
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date)=2012
          AND banking_transaction_id IS NULL
          AND ABS(COALESCE(gross_amount,0)-%s)<0.01
          AND receipt_date BETWEEN (%s::date - INTERVAL '2 day') AND (%s::date + INTERVAL '2 day')
        LIMIT 20
        """, (tx['debit_amount'], tx['transaction_date'], tx['transaction_date']))
        cands=cur.fetchall()

        token_matched=[]
        for c in cands:
            hay=f"{(c['vendor_name'] or '').upper()} {(c['description'] or '').upper()}"
            if any(tok in hay for tok in tokens):
                token_matched.append(c)

        if len(token_matched)==1:
            rid=token_matched[0]['receipt_id']
            token_links.append({
                'transaction_id': tx['transaction_id'],
                'transaction_date': tx['transaction_date'],
                'amount': float(tx['debit_amount']),
                'receipt_id': rid,
                'tokens': ' '.join(tokens),
                'description': desc,
            })

    for m in token_links:
        cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s AND banking_transaction_id IS NULL", (m['transaction_id'], m['receipt_id']))
        cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s AND receipt_id IS NULL", (m['receipt_id'], m['transaction_id']))

    conn.commit()

    hcsv=out_dir / f'2012_heffner_strict_links_{stamp}.csv'
    with hcsv.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['transaction_id','transaction_date','amount','receipt_id','receipt_date','description'])
        w.writeheader(); w.writerows(heffner_links)

    tcsv=out_dir / f'2012_blank_vendor_token_links_{stamp}.csv'
    with tcsv.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['transaction_id','transaction_date','amount','receipt_id','tokens','description'])
        w.writeheader(); w.writerows(token_links)

    cur.execute("""
    SELECT COUNT(*) AS rows_no_receipt, COALESCE(SUM(debit_amount),0) AS amt_no_receipt
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date)=2012
      AND COALESCE(debit_amount,0)>0
      AND receipt_id IS NULL
    """)
    rem=cur.fetchone()

    print('2012_heffner_links_applied:', len(heffner_links))
    print('2012_heffner_links_csv:', hcsv)
    print('2012_blank_vendor_token_links_applied:', len(token_links))
    print('2012_blank_vendor_token_links_csv:', tcsv)
    print('2012_unlinked_debits_remaining:', dict(rem))

except Exception:
    conn.rollback()
    raise
finally:
    cur.close(); conn.close()
