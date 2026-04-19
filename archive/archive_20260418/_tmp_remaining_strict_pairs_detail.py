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
rows=cur.fetchall(); a=[r for r in rows if r['account_number'] in ('0228362','8362')]; b=[r for r in rows if r['account_number']=='1615']

pairs=[]
for x in a:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    sig=('1615' in (x['source_file']+' '+x['import_batch']+' '+x['description']))
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount'])) >= Decimal('0.01'): continue
        dd=abs((x['transaction_date']-y['transaction_date']).days)
        if dd!=0: continue
        inter=xt & norm_tokens(y['vendor_extracted']+' '+y['description'])
        exact_desc=(x['description'].strip().upper()==y['description'].strip().upper())
        strong=sig or exact_desc or (len(inter)>=2)
        risky=any(k in (x['description']+' '+y['description']).upper() for k in ['WITHDRAWAL','ABM','ATM','CASH'])
        if strong and not (risky and not sig):
            pairs.append((x,y,dd,len(inter),sig,exact_desc,risky))

print('remaining_strict_pairs', len(pairs))
with_receipts=0
for x,y,*_ in pairs:
    cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id IN (%s,%s)", (x['transaction_id'], y['transaction_id']))
    c=cur.fetchone()['c']
    if c>0:
        with_receipts+=1
print('remaining_pairs_with_any_receipts', with_receipts)

for x,y,dd,ov,sig,ed,risky in pairs[:120]:
    cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id=%s", (x['transaction_id'],)); c8362=cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id=%s", (y['transaction_id'],)); c1615=cur.fetchone()['c']
    print({'tx8362':x['transaction_id'],'tx1615':y['transaction_id'],'year':x['transaction_date'].year,'amt':float(x['debit_amount']),'desc8362':x['description'],'desc1615':y['description'],'ov':ov,'sig':sig,'risky':risky,'r8362':c8362,'r1615':c1615})

cur.close(); conn.close()
