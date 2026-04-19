import re
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor

DRY_RUN = False
YEARS = (2012, 2012)
TAG = 'auto_dedupe_8362_to_1615_2012'

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


def is_review_receipt(r):
    src=(r['receipt_source'] or '').lower()
    vendor=(r['vendor_name'] or '').upper()
    return ('unlinked' in vendor) or ('review' in vendor) or src.startswith('auto_') or bool(r['exclude_from_reports'])


def pick_chosen(receipts, tx1615):
    on1615=[r for r in receipts if r['banking_transaction_id']==tx1615]
    nonrev1615=[r for r in on1615 if not is_review_receipt(r)]
    if nonrev1615:
        return sorted(nonrev1615, key=lambda r:r['receipt_id'])[0]
    nonrev=[r for r in receipts if not is_review_receipt(r)]
    if nonrev:
        # prefer already linked to 1615, then oldest id
        return sorted(nonrev, key=lambda r:(0 if r['banking_transaction_id']==tx1615 else 1, r['receipt_id']))[0]
    if on1615:
        return sorted(on1615, key=lambda r:r['receipt_id'])[0]
    return sorted(receipts, key=lambda r:r['receipt_id'])[0]

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

apply_pairs=[]
for a,b,dd,ov in final:
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
    chosen=pick_chosen(rs, b['transaction_id'])
    apply_pairs.append((a,b,chosen,rs))

print('unambiguous_pairs', len(final))
print('apply_pairs_with_receipts', len(apply_pairs))

# Apply
report=[]
for a,b,chosen,rs in apply_pairs:
    tx8362=a['transaction_id']; tx1615=b['transaction_id']; rid_keep=chosen['receipt_id']

    # Move keep receipt to canonical tx
    cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s", (tx1615, rid_keep))

    # Unlink all other receipts currently on tx8362
    cur.execute("""
        UPDATE receipts
        SET banking_transaction_id=NULL
        WHERE banking_transaction_id=%s
          AND receipt_id<>%s
    """, (tx8362, rid_keep))
    unlinked=cur.rowcount

    # If keep receipt had an rbl on tx8362, move it to tx1615 unless already exists
    cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (rid_keep, tx1615))
    has_target=cur.fetchone()['c']>0
    cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (rid_keep, tx8362))
    has_src=cur.fetchone()['c']>0
    moved=0
    if has_src and not has_target:
        cur.execute("UPDATE receipt_banking_links SET transaction_id=%s WHERE receipt_id=%s AND transaction_id=%s", (tx1615, rid_keep, tx8362))
        moved=cur.rowcount

    # Remove all residual links pointing at doomed tx8362
    cur.execute("DELETE FROM receipt_banking_links WHERE transaction_id=%s", (tx8362,))
    deleted_links=cur.rowcount

    # Keep transaction receipt pointer coherent
    cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s", (rid_keep, tx1615))

    # Delete contaminated 8362 tx
    cur.execute("DELETE FROM banking_transactions WHERE transaction_id=%s", (tx8362,))
    deleted_tx=cur.rowcount

    report.append({
        'tx8362':tx8362,'tx1615':tx1615,'keep_receipt':rid_keep,
        'unlinked_receipts':unlinked,'moved_rbl':moved,'deleted_rbl':deleted_links,'deleted_tx':deleted_tx,
        'amt':float(a['debit_amount']),'d8362':str(a['transaction_date']),'d1615':str(b['transaction_date'])
    })

if DRY_RUN:
    conn.rollback()
    print('DRY RUN rollback')
else:
    conn.commit()
    print('APPLIED and committed')

print('deleted_transactions', sum(r['deleted_tx'] for r in report))
print('total_unlinked_receipts', sum(r['unlinked_receipts'] for r in report))
print('total_deleted_rbl', sum(r['deleted_rbl'] for r in report))
for r in report:
    print(r)

# post-check remaining 2012 matches with same rule
cur2=conn.cursor(cursor_factory=RealDictCursor)
cur2.execute("""
SELECT transaction_id, account_number, transaction_date, COALESCE(debit_amount,0) AS debit_amount,
       COALESCE(vendor_extracted,'') AS vendor_extracted, COALESCE(description,'') AS description
FROM banking_transactions
WHERE EXTRACT(YEAR FROM transaction_date) BETWEEN %s AND %s
  AND account_number IN ('0228362','8362','1615')
  AND COALESCE(debit_amount,0) > 0
ORDER BY transaction_date, transaction_id
""", YEARS)
rows=cur2.fetchall()
a=[r for r in rows if r['account_number'] in ('0228362','8362')]
b=[r for r in rows if r['account_number']=='1615']
rem=0
for x in a:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    if not xt: continue
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount']))>=Decimal('0.01'): continue
        if abs((x['transaction_date']-y['transaction_date']).days)>3: continue
        yt=norm_tokens(y['vendor_extracted']+' '+y['description'])
        if xt & yt:
            rem += 1
print('remaining_candidate_pairs_2012', rem)

cur2.close(); cur.close(); conn.close()
