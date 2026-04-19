import re
from decimal import Decimal
from collections import defaultdict
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
       COALESCE(vendor_extracted,'') AS vendor_extracted, COALESCE(description,'') AS description,
       COALESCE(source_file,'') AS source_file, COALESCE(import_batch,'') AS import_batch
FROM banking_transactions
WHERE account_number IN ('0228362','8362','1615')
  AND COALESCE(debit_amount,0) > 0
ORDER BY transaction_date, transaction_id
""")
rows=cur.fetchall()
a=[r for r in rows if r['account_number'] in ('0228362','8362')]
b=[r for r in rows if r['account_number']=='1615']

cands=[]
for x in a:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    has1615signal=('1615' in (x['source_file']+' '+x['import_batch']+' '+x['description']))
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount'])) >= Decimal('0.01'): continue
        dd=abs((x['transaction_date']-y['transaction_date']).days)
        if dd>3: continue
        inter=xt & norm_tokens(y['vendor_extracted']+' '+y['description'])
        if not inter and not has1615signal: continue
        cands.append((x,y,dd,len(inter),has1615signal))

# one-to-one unambiguous
by_a=defaultdict(list); by_b=defaultdict(list)
for c in cands:
    by_a[c[0]['transaction_id']].append(c)
    by_b[c[1]['transaction_id']].append(c)
base=[]
for aid,lst in by_a.items():
    lst=sorted(lst, key=lambda x:(x[2], -x[3], 0 if x[4] else 1, x[1]['transaction_id']))
    if len(lst)>1 and (lst[1][2],lst[1][3],lst[1][4])==(lst[0][2],lst[0][3],lst[0][4]):
        continue
    base.append(lst[0])
final=[]
for c in base:
    bid=c[1]['transaction_id']
    lst=sorted(by_b[bid], key=lambda x:(x[2], -x[3], 0 if x[4] else 1, x[0]['transaction_id']))
    if lst and lst[0][0]['transaction_id']==c[0]['transaction_id']:
        if len(lst)>1 and (lst[1][2],lst[1][3],lst[1][4])==(lst[0][2],lst[0][3],lst[0][4]):
            continue
        final.append(c)

# strict safety subset
safe=[]
for x,y,dd,ov,sig in final:
    exact_day = (dd==0)
    exact_desc = (x['description'].strip().upper()==y['description'].strip().upper())
    strong = sig or exact_desc or (ov>=2)
    # avoid potential legitimate ambiguous cash-like rows unless strong signal
    risky = any(k in (x['description']+' '+y['description']).upper() for k in ['WITHDRAWAL','ABM','ATM','CASH'])
    if exact_day and strong and not (risky and not sig):
        safe.append((x,y,dd,ov,sig,exact_desc,risky))

print('unambiguous_pairs', len(final))
print('strict_safe_pairs', len(safe))

# receipt presence check
safe_with_receipts=0
safe_no_receipts=0
for x,y,*_ in safe:
    cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id IN (%s,%s)", (x['transaction_id'],y['transaction_id']))
    if cur.fetchone()['c']>0:
        safe_with_receipts+=1
    else:
        safe_no_receipts+=1
print('strict_safe_with_receipts', safe_with_receipts)
print('strict_safe_no_receipts', safe_no_receipts)

by_year=defaultdict(int)
for x,_,*rest in safe:
    by_year[x['transaction_date'].year]+=1
print('strict_year_breakdown', dict(sorted(by_year.items())))

# sample
for x,y,dd,ov,sig,ed,risky in safe[:60]:
    print({'tx8362':x['transaction_id'],'tx1615':y['transaction_id'],'year':x['transaction_date'].year,'amt':float(x['debit_amount']),'desc8362':x['description'],'desc1615':y['description'],'sig1615':sig,'ov':ov,'exact_desc':ed,'risky_cashlike':risky})

cur.close(); conn.close()
