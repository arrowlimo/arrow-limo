import re
import psycopg2
from psycopg2.extras import RealDictCursor

stop={'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','DEBIT','CREDIT','ELECTRONIC','FUNDS','TRANSFER','INTERNET','BANKING'}


def norm_tokens(text):
    s=(text or '').upper()
    toks=re.findall(r"[A-Z][A-Z'&.-]{2,}", s)
    out=[]
    for t in toks:
        if t in stop or t.isdigit():
            continue
        if len(t)>=3:
            out.append(t)
    return set(out)

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
cur=conn.cursor(cursor_factory=RealDictCursor)
cur.execute("""
SELECT transaction_id, account_number, transaction_date, COALESCE(debit_amount,0) AS debit_amount,
       COALESCE(vendor_extracted,'' ) AS vendor_extracted,
       COALESCE(description,'') AS description,
       COALESCE(receipt_id,0) AS receipt_id
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date)=2012
  AND account_number IN ('0228362','8362','1615')
  AND COALESCE(debit_amount,0) > 0
ORDER BY transaction_date, transaction_id
""")
rows=cur.fetchall()
a=[r for r in rows if r['account_number'] in ('0228362','8362')]
b=[r for r in rows if r['account_number']=='1615']

pairs=[]
for x in a:
    xt=norm_tokens((x['vendor_extracted']+' '+x['description']).strip())
    for y in b:
        if abs(float(x['debit_amount'])-float(y['debit_amount']))>=0.01:
            continue
        day=abs((x['transaction_date']-y['transaction_date']).days)
        if day>3:
            continue
        yt=norm_tokens((y['vendor_extracted']+' '+y['description']).strip())
        if not xt or not yt:
            continue
        inter=xt & yt
        if not inter:
            continue
        pairs.append((x,y,day,sorted(inter)))

print('2012_candidate_pairs:', len(pairs))
for x,y,day,inter in pairs[:80]:
    print({'tx8362':x['transaction_id'],'d8362':x['transaction_date'],'tx1615':y['transaction_id'],'d1615':y['transaction_date'],'amt':float(x['debit_amount']),'overlap':inter,'r8362':x['receipt_id'],'r1615':y['receipt_id'],'desc8362':x['description'],'desc1615':y['description']})

cur.close(); conn.close()
