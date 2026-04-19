import re
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

stop={'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','DEBIT','CREDIT','ELECTRONIC','FUNDS','TRANSFER','INTERNET','BANKING','STORE'}

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

cur.execute("SELECT transaction_id, account_number, transaction_date, debit_amount, description FROM banking_transactions WHERE transaction_id IN (97112,100042)")
print('known_pair_rows:')
for r in cur.fetchall():
    print(dict(r))

cur.execute("""
SELECT transaction_id, account_number, transaction_date, COALESCE(debit_amount,0) AS debit_amount,
       COALESCE(vendor_extracted,'') AS vendor_extracted, COALESCE(description,'') AS description
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
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    if not xt: continue
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount']))>=Decimal('0.01'): continue
        if abs((x['transaction_date']-y['transaction_date']).days)>3: continue
        yt=norm_tokens(y['vendor_extracted']+' '+y['description'])
        inter=xt & yt
        if inter:
            pairs.append((x,y,sorted(inter)))

print('\nremaining_pairs_detail:', len(pairs))
for x,y,inter in pairs:
    print({'tx8362':x['transaction_id'],'d8362':x['transaction_date'],'tx1615':y['transaction_id'],'d1615':y['transaction_date'],'amt':float(x['debit_amount']),'overlap':inter,'desc8362':x['description'],'desc1615':y['description']})

cur.close(); conn.close()
