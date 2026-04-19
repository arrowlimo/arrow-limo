import re
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

stop={'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','DEBIT','CREDIT','ELECTRONIC','FUNDS','TRANSFER','INTERNET','BANKING','STORE','POS'}

def norm_tokens(text):
    s=(text or '').upper(); toks=re.findall(r"[A-Z][A-Z'&.-]{2,}", s)
    return {t for t in toks if t not in stop and not t.isdigit() and len(t)>=3}

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT transaction_id, account_number, transaction_date, COALESCE(debit_amount,0) AS debit_amount,
       COALESCE(vendor_extracted,'') AS vendor_extracted, COALESCE(description,'') AS description
FROM banking_transactions
WHERE account_number IN ('0228362','8362','1615')
  AND COALESCE(debit_amount,0) > 0
ORDER BY transaction_date, transaction_id
""")
rows=cur.fetchall(); a=[r for r in rows if r['account_number'] in ('0228362','8362')]; b=[r for r in rows if r['account_number']=='1615']

pairs=[]
for x in a:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    if not xt: continue
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount'])) >= Decimal('0.01'): continue
        dd=abs((x['transaction_date']-y['transaction_date']).days)
        if dd>3: continue
        inter=xt & norm_tokens(y['vendor_extracted']+' '+y['description'])
        if not inter: continue
        cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id IN (%s,%s)", (x['transaction_id'], y['transaction_id']))
        rc=cur.fetchone()['c']
        if rc>0:
            pairs.append((x['transaction_id'],y['transaction_id'],x['transaction_date'].year,float(x['debit_amount']),dd,len(inter),rc,x['description'],y['description']))

print('remaining_3day_pairs_with_any_receipts', len(pairs))
for p in pairs[:80]:
    print({'tx8362':p[0],'tx1615':p[1],'year':p[2],'amt':p[3],'day_gap':p[4],'ov':p[5],'receipt_count':p[6],'desc8362':p[7],'desc1615':p[8]})

cur.close(); conn.close()
