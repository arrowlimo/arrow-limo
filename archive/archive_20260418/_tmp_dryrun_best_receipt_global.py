import re
from decimal import Decimal
from collections import defaultdict
import psycopg2
from psycopg2.extras import RealDictCursor

stop={'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','DEBIT','CREDIT','ELECTRONIC','FUNDS','TRANSFER','INTERNET','BANKING','STORE','POS'}

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
    src=(r.get('receipt_source') or '').lower()
    vendor=(r.get('vendor_name') or '').upper()
    return ('unlinked' in vendor) or ('review' in vendor) or src.startswith('auto_') or bool(r.get('exclude_from_reports'))

def vendor_match_score(r, canonical_tx):
    rv = f"{r.get('canonical_vendor') or ''} {r.get('vendor_name') or ''} {r.get('description') or ''}"
    tv = f"{canonical_tx.get('vendor_extracted') or ''} {canonical_tx.get('description') or ''}"
    return len(norm_tokens(rv) & norm_tokens(tv))

def date_gap_days(r, canonical_tx):
    rd = r.get('receipt_date')
    td = canonical_tx.get('transaction_date')
    if not rd or not td:
        return 9999
    return abs((rd - td).days)

def amount_exact_match(r, canonical_tx):
    amt = r.get('gross_amount')
    tx_amt = canonical_tx.get('debit_amount')
    if amt is None or tx_amt is None:
        return False
    return abs(Decimal(str(amt)) - Decimal(str(tx_amt))) < Decimal('0.01')

def receipt_quality_score(r, canonical_tx_id):
    s=0
    if r.get('canonical_vendor'): s += 25
    if r.get('gl_account_code') or r.get('gl_code'): s += 35
    if r.get('fuel') is True or (r.get('fuel_amount') or 0) > 0: s += 20
    if r.get('is_split_receipt') is True or (r.get('split_key') is not None) or (r.get('split_group_id') is not None): s += 20
    if r.get('receipt_review_notes'): s += 10
    if (r.get('description') and str(r.get('description')).strip()): s += 8
    if not r.get('exclude_from_reports'): s += 10
    if (r.get('receipt_source') or '') == 'BANKING': s += 8
    if r.get('banking_transaction_id') == canonical_tx_id: s += 5
    if is_review_receipt(r): s -= 120
    return s

def pick_best_receipt(receipts, canonical_tx):
    # Priority requested: exact amount -> vendor match -> date match.
    ordered=sorted(
        receipts,
        key=lambda r: (
            is_review_receipt(r),
            0 if amount_exact_match(r, canonical_tx) else 1,
            -vendor_match_score(r, canonical_tx),
            date_gap_days(r, canonical_tx),
            -receipt_quality_score(r, canonical_tx['transaction_id']),
            r['receipt_id'],
        ),
    )
    return ordered[0]

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

rows8362=[r for r in rows if r['account_number'] in ('0228362','8362')]
rows1615=[r for r in rows if r['account_number']=='1615']

cands=[]
for a in rows8362:
    at=norm_tokens(a['vendor_extracted']+' '+a['description'])
    has1615signal=('1615' in (a['source_file']+' '+a['import_batch']+' '+a['description']))
    for b in rows1615:
        if abs(Decimal(a['debit_amount'])-Decimal(b['debit_amount'])) >= Decimal('0.01'):
            continue
        dd=abs((a['transaction_date']-b['transaction_date']).days)
        if dd>3:
            continue
        bt=norm_tokens(b['vendor_extracted']+' '+b['description'])
        inter=at & bt
        if inter or has1615signal:
            cands.append((a,b,dd,len(inter),has1615signal))

# Unambiguous pairing rules
by_a=defaultdict(list)
by_b=defaultdict(list)
for c in cands:
    by_a[c[0]['transaction_id']].append(c)
    by_b[c[1]['transaction_id']].append(c)

selected=[]
for aid, lst in by_a.items():
    lst=sorted(lst, key=lambda x:(x[2], -x[3], 0 if x[4] else 1, x[1]['transaction_id']))
    best=lst[0]
    if len(lst)>1 and (lst[1][2],lst[1][3],lst[1][4])==(best[2],best[3],best[4]):
        continue
    selected.append(best)

final=[]
for c in selected:
    bid=c[1]['transaction_id']
    lst=sorted(by_b[bid], key=lambda x:(x[2], -x[3], 0 if x[4] else 1, x[0]['transaction_id']))
    if lst and lst[0][0]['transaction_id']==c[0]['transaction_id']:
        if len(lst)>1 and (lst[1][2],lst[1][3],lst[1][4])==(lst[0][2],lst[0][3],lst[0][4]):
            continue
        final.append(c)

print('total_candidates', len(cands))
print('unambiguous_pairs', len(final))

# quality analysis
pairs=[]
for a,b,dd,ov,sig in final:
    cur.execute("""
        SELECT receipt_id, vendor_name, canonical_vendor, description, gross_amount, receipt_date,
               banking_transaction_id, receipt_source, exclude_from_reports,
               gl_account_code, gl_code, fuel, fuel_amount, split_key, split_group_id,
               is_split_receipt, receipt_review_notes
        FROM receipts
        WHERE banking_transaction_id IN (%s,%s)
        ORDER BY receipt_id
    """, (a['transaction_id'], b['transaction_id']))
    rs=cur.fetchall()
    if not rs:
        continue
    best=pick_best_receipt(rs, b)
    pairs.append((a,b,best,rs,dd,ov,sig))

print('pairs_with_receipts', len(pairs))

# summarize by year
year_counts=defaultdict(int)
for a,b,_,_,_,_,_ in pairs:
    year_counts[a['transaction_date'].year]+=1
print('year_breakdown', dict(sorted(year_counts.items())))

for a,b,best,rs,dd,ov,sig in pairs[:80]:
    print({
        'tx8362':a['transaction_id'],'tx1615':b['transaction_id'],'year':a['transaction_date'].year,
        'amt':float(a['debit_amount']),'d8362':str(a['transaction_date']),'d1615':str(b['transaction_date']),
        'day_gap':dd,'token_overlap':ov,'has1615signal':sig,
        'best_receipt':best['receipt_id'],'best_vendor':best['vendor_name'],
        'best_gl':best['gl_account_code'] or best['gl_code'],'best_split':best['is_split_receipt']
    })

cur.close(); conn.close()
