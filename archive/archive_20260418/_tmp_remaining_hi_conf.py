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

hi=[]
for x in a:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount']))>=Decimal('0.01'): continue
        dd=abs((x['transaction_date']-y['transaction_date']).days)
        if dd>3: continue
        ov=len(xt & norm_tokens(y['vendor_extracted']+' '+y['description']))
        if ov<2: continue
        cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id=%s", (x['transaction_id'],))
        r8362=cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id=%s", (y['transaction_id'],))
        r1615=cur.fetchone()['c']
        hi.append((x['transaction_id'],y['transaction_id'],x['transaction_date'].year,float(x['debit_amount']),dd,ov,r8362,r1615,x['description'],y['description']))

print('remaining_high_confidence_pairs_ov2_within3d', len(hi))
with_8362_receipt=sum(1 for r in hi if r[6]>0)
print('remaining_high_confidence_pairs_where_8362_has_receipt', with_8362_receipt)
for r in hi[:80]:
    print({'tx8362':r[0],'tx1615':r[1],'year':r[2],'amt':r[3],'day_gap':r[4],'ov':r[5],'r8362':r[6],'r1615':r[7],'desc8362':r[8],'desc1615':r[9]})

cur.close(); conn.close()
