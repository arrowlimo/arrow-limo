import psycopg2
from psycopg2.extras import RealDictCursor

# manual resolution of ambiguous leftovers
# 97153 (NSF Fee) -> keep 1615 entries; remove 8362 copy
# 97176 (Ranch House) -> keep 1615 tx 95057 non-review; remove 8362 copy

to_delete=[97153,97176]

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

for tx in to_delete:
    cur.execute("SELECT transaction_id, account_number, transaction_date, debit_amount, description FROM banking_transactions WHERE transaction_id=%s", (tx,))
    r=cur.fetchone()
    print('delete_target', dict(r) if r else None)
    if not r:
        continue
    cur.execute("UPDATE receipts SET banking_transaction_id=NULL WHERE banking_transaction_id=%s", (tx,))
    print(' unlinked_receipts', cur.rowcount)
    cur.execute("DELETE FROM receipt_banking_links WHERE transaction_id=%s", (tx,))
    print(' deleted_rbl', cur.rowcount)
    cur.execute("DELETE FROM banking_transactions WHERE transaction_id=%s", (tx,))
    print(' deleted_tx', cur.rowcount)

conn.commit()
print('committed')

# verify no 2012 collisions remain by same amount +-3d and vendor token overlap
import re
from decimal import Decimal
stop={'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','DEBIT','CREDIT','ELECTRONIC','FUNDS','TRANSFER','INTERNET','BANKING','STORE'}

def norm_tokens(text):
    s=(text or '').upper(); toks=re.findall(r"[A-Z][A-Z'&.-]{2,}", s); out=[]
    for t in toks:
        if t in stop or t.isdigit():
            continue
        if len(t)>=3:
            out.append(t)
    return set(out)

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
a=[x for x in rows if x['account_number'] in ('0228362','8362')]
b=[x for x in rows if x['account_number']=='1615']
rem=[]
for x in a:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    if not xt: continue
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount']))>=Decimal('0.01'): continue
        if abs((x['transaction_date']-y['transaction_date']).days)>3: continue
        inter=xt & norm_tokens(y['vendor_extracted']+' '+y['description'])
        if inter:
            rem.append((x['transaction_id'],y['transaction_id'],float(x['debit_amount']),sorted(inter)))
print('remaining_pairs_2012', len(rem))
for r in rem[:20]:
    print(r)

cur.close(); conn.close()
