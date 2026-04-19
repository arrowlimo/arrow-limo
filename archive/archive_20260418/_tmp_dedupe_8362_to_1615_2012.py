import re
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

DRY_RUN = True
YEARS = (2012, 2012)

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


def receipt_score(r):
    score=0
    src=(r['receipt_source'] or '').lower()
    vendor=(r['vendor_name'] or '').upper()
    if 'unlinked' in vendor or 'review' in vendor:
        score -= 100
    if src.startswith('auto_'):
        score -= 50
    if src=='BANKING':
        score += 30
    if not r['exclude_from_reports']:
        score += 20
    if r['banking_transaction_id'] is not None:
        score += 10
    return score

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
SELECT transaction_id, account_number, transaction_date, COALESCE(debit_amount,0) AS debit_amount,
       COALESCE(vendor_extracted,'') AS vendor_extracted, COALESCE(description,'') AS description
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN %s AND %s
  AND account_number IN ('0228362','8362','1615')
  AND COALESCE(debit_amount,0) > 0
ORDER BY transaction_date, transaction_id
""", YEARS)
rows=cur.fetchall()
rows8362=[r for r in rows if r['account_number'] in ('0228362','8362')]
rows1615=[r for r in rows if r['account_number']=='1615']

# Build candidates
cands=[]
for a in rows8362:
    at=norm_tokens(a['vendor_extracted']+' '+a['description'])
    if not at:
        continue
    for b in rows1615:
        if abs(Decimal(a['debit_amount'])-Decimal(b['debit_amount'])) >= Decimal('0.01'):
            continue
        dd=abs((a['transaction_date']-b['transaction_date']).days)
        if dd>3:
            continue
        bt=norm_tokens(b['vendor_extracted']+' '+b['description'])
        inter=at & bt
        if not inter:
            continue
        cands.append((a,b,dd,len(inter)))

# Keep only unambiguous nearest by both sides
from collections import defaultdict
by_a=defaultdict(list)
by_b=defaultdict(list)
for c in cands:
    by_a[c[0]['transaction_id']].append(c)
    by_b[c[1]['transaction_id']].append(c)

selected=[]
for aid, lst in by_a.items():
    lst=sorted(lst, key=lambda x:(x[2], -x[3], x[1]['transaction_id']))
    best=lst[0]
    # strict ambiguity guard
    if len(lst)>1 and (lst[1][2],lst[1][3])==(best[2],best[3]):
        continue
    selected.append(best)

final=[]
for c in selected:
    bid=c[1]['transaction_id']
    lst=sorted(by_b[bid], key=lambda x:(x[2], -x[3], x[0]['transaction_id']))
    if lst and lst[0][0]['transaction_id']==c[0]['transaction_id']:
        if len(lst)>1 and (lst[1][2],lst[1][3])==(lst[0][2],lst[0][3]):
            continue
        final.append(c)

print('candidate_pairs_total', len(cands))
print('selected_unambiguous_pairs', len(final))

pairs=[]
for a,b,dd,ov in final:
    # linked receipts to either tx
    cur.execute("""
        SELECT receipt_id, vendor_name, gross_amount, receipt_date, banking_transaction_id,
               receipt_source, exclude_from_reports
        FROM receipts
        WHERE banking_transaction_id IN (%s,%s)
        ORDER BY receipt_id
    """, (a['transaction_id'], b['transaction_id']))
    rs=cur.fetchall()
    if not rs:
        continue
    chosen=max(rs, key=receipt_score)
    pairs.append((a,b,chosen,rs,dd,ov))

print('pairs_with_receipts', len(pairs))

# dry run actions
unlink_receipt_ids=[]
move_link_rows=0
delete_link_rows=0
delete_tx_ids=[]
for a,b,chosen,rs,dd,ov in pairs:
    delete_tx_ids.append(a['transaction_id'])
    for r in rs:
        if r['receipt_id']==chosen['receipt_id']:
            continue
        if r['banking_transaction_id']==a['transaction_id']:
            unlink_receipt_ids.append(r['receipt_id'])
    # rbl counts
    cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE transaction_id=%s", (a['transaction_id'],))
    c8362=cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE transaction_id=%s AND receipt_id=%s", (b['transaction_id'], chosen['receipt_id']))
    has_target=cur.fetchone()['c']>0
    cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE transaction_id=%s AND receipt_id=%s", (a['transaction_id'], chosen['receipt_id']))
    has_src=cur.fetchone()['c']>0
    if has_src and not has_target:
        move_link_rows += 1
    # remaining rows on 8362 tx will be deleted
    delete_link_rows += c8362

print('would_delete_8362_transactions', len(set(delete_tx_ids)))
print('would_unlink_receipts_from_8362', len(set(unlink_receipt_ids)))
print('would_move_chosen_rbl_rows', move_link_rows)
print('would_delete_rbl_rows_on_8362', delete_link_rows)

for a,b,chosen,rs,dd,ov in pairs[:40]:
    print({
        'del8362':a['transaction_id'],'keep1615':b['transaction_id'],'amt':float(a['debit_amount']),
        'd8362':str(a['transaction_date']),'d1615':str(b['transaction_date']),'day_gap':dd,
        'chosen_receipt':chosen['receipt_id'],'chosen_vendor':chosen['vendor_name'],
        'overlap':ov,'desc8362':a['description'],'desc1615':b['description']
    })

if DRY_RUN:
    conn.rollback()
else:
    conn.commit()

cur.close(); conn.close()
