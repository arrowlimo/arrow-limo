import re
from decimal import Decimal
from collections import defaultdict
import psycopg2
from psycopg2.extras import RealDictCursor

DRY_RUN=False

stop={'POINT','OF','SALE','INTERAC','RETAIL','PURCHASE','BRANCH','TRANSACTION','DEBIT','CREDIT','ELECTRONIC','FUNDS','TRANSFER','INTERNET','BANKING','STORE','POS'}

def norm_tokens(text):
    s=(text or '').upper(); toks=re.findall(r"[A-Z][A-Z'&.-]{2,}", s)
    return {t for t in toks if t not in stop and not t.isdigit() and len(t)>=3}

def is_review_receipt(r):
    src=(r.get('receipt_source') or '').lower()
    vendor=(r.get('vendor_name') or '').upper()
    return ('unlinked' in vendor) or ('review' in vendor) or src.startswith('auto_') or bool(r.get('exclude_from_reports'))

def receipt_quality_score(r, canonical_tx):
    s=0
    if r.get('canonical_vendor'): s += 25
    if r.get('gl_account_code') or r.get('gl_code'): s += 35
    if r.get('fuel') is True or (r.get('fuel_amount') or 0) > 0: s += 20
    if r.get('is_split_receipt') is True or (r.get('split_key') is not None) or (r.get('split_group_id') is not None): s += 20
    if r.get('receipt_review_notes'): s += 10
    if (r.get('description') and str(r.get('description')).strip()): s += 8
    if not r.get('exclude_from_reports'): s += 10
    if (r.get('receipt_source') or '') == 'BANKING': s += 8
    if r.get('banking_transaction_id') == canonical_tx: s += 5
    if is_review_receipt(r): s -= 120
    return s

def pick_best_receipt(receipts, canonical_tx):
    ordered=sorted(receipts, key=lambda r:(is_review_receipt(r), -receipt_quality_score(r, canonical_tx), r['receipt_id']))
    return ordered[0]

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

# FK tables that directly reference banking_transactions
cur.execute("""
SELECT conrelid::regclass::text AS tbl, a.attname AS col
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE c.contype='f' AND c.confrelid='banking_transactions'::regclass
ORDER BY 1,2
""")
fk_targets=[(r['tbl'], r['col']) for r in cur.fetchall()]

# We'll handle receipts/receipt_banking_links custom; remap the rest generically.
skip_generic={('receipts','banking_transaction_id'),('receipt_banking_links','transaction_id')}
extra_targets=[x for x in fk_targets if x not in skip_generic]

# Build candidate pairs
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
for x in rows8362:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    sig=('1615' in (x['source_file']+' '+x['import_batch']+' '+x['description']))
    for y in rows1615:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount'])) >= Decimal('0.01'): continue
        dd=abs((x['transaction_date']-y['transaction_date']).days)
        if dd>3: continue
        inter=xt & norm_tokens(y['vendor_extracted']+' '+y['description'])
        if inter or sig:
            cands.append((x,y,dd,len(inter),sig))

# one-to-one unambiguous
by_a=defaultdict(list); by_b=defaultdict(list)
for c in cands:
    by_a[c[0]['transaction_id']].append(c); by_b[c[1]['transaction_id']].append(c)
selected=[]
for aid,lst in by_a.items():
    lst=sorted(lst, key=lambda x:(x[2], -x[3], 0 if x[4] else 1, x[1]['transaction_id']))
    if len(lst)>1 and (lst[1][2],lst[1][3],lst[1][4])==(lst[0][2],lst[0][3],lst[0][4]):
        continue
    selected.append(lst[0])
final=[]
for c in selected:
    bid=c[1]['transaction_id']
    lst=sorted(by_b[bid], key=lambda x:(x[2], -x[3], 0 if x[4] else 1, x[0]['transaction_id']))
    if lst and lst[0][0]['transaction_id']==c[0]['transaction_id']:
        if len(lst)>1 and (lst[1][2],lst[1][3],lst[1][4])==(lst[0][2],lst[0][3],lst[0][4]):
            continue
        final.append(c)

# strict safety filter
safe=[]
for x,y,dd,ov,sig in final:
    exact_day=(dd==0)
    exact_desc=(x['description'].strip().upper()==y['description'].strip().upper())
    strong=sig or exact_desc or (ov>=2)
    risky=any(k in (x['description']+' '+y['description']).upper() for k in ['WITHDRAWAL','ABM','ATM','CASH'])
    if exact_day and strong and not (risky and not sig):
        safe.append((x,y,dd,ov,sig))

# receipts required for "best receipt" logic
apply_pairs=[]
for x,y,dd,ov,sig in safe:
    cur.execute("""
    SELECT receipt_id, vendor_name, canonical_vendor, description, gross_amount, receipt_date,
           banking_transaction_id, receipt_source, exclude_from_reports,
           gl_account_code, gl_code, fuel, fuel_amount, split_key, split_group_id,
           is_split_receipt, receipt_review_notes
    FROM receipts
    WHERE banking_transaction_id IN (%s,%s)
    ORDER BY receipt_id
    """, (x['transaction_id'], y['transaction_id']))
    rs=cur.fetchall()
    if not rs:
        continue
    best=pick_best_receipt(rs, y['transaction_id'])
    apply_pairs.append((x,y,best,rs))

print('apply_pairs_with_receipts', len(apply_pairs))

applied=[]
skipped=[]
for x,y,best,rs in apply_pairs:
    tx_bad=x['transaction_id']; tx_good=y['transaction_id']; keep_rid=best['receipt_id']
    cur.execute('SAVEPOINT pair_sp')
    try:
        # best receipt to canonical tx
        cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s", (tx_good, keep_rid))
        # unlink all others on bad tx
        cur.execute("UPDATE receipts SET banking_transaction_id=NULL WHERE banking_transaction_id=%s AND receipt_id<>%s", (tx_bad, keep_rid))
        unlinked=cur.rowcount

        # handle receipt_banking_links carefully
        cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (keep_rid, tx_good))
        has_good=cur.fetchone()['c']>0
        cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (keep_rid, tx_bad))
        has_bad=cur.fetchone()['c']>0
        moved=0
        if has_bad and not has_good:
            cur.execute("UPDATE receipt_banking_links SET transaction_id=%s WHERE receipt_id=%s AND transaction_id=%s", (tx_good, keep_rid, tx_bad))
            moved=cur.rowcount
        cur.execute("DELETE FROM receipt_banking_links WHERE transaction_id=%s", (tx_bad,))
        del_rbl=cur.rowcount

        # remap all other FK refs bad->good
        remap_counts={}
        for tbl,col in extra_targets:
            q=f"UPDATE {tbl} SET {col}=%s WHERE {col}=%s"
            cur.execute(q, (tx_good, tx_bad))
            if cur.rowcount:
                remap_counts[f'{tbl}.{col}']=cur.rowcount

        # keep canonical pointer
        cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s", (keep_rid, tx_good))

        # delete bad row
        cur.execute("DELETE FROM banking_transactions WHERE transaction_id=%s", (tx_bad,))
        if cur.rowcount != 1:
            raise Exception('delete_failed')

        applied.append({
            'tx_bad':tx_bad,'tx_good':tx_good,'keep_rid':keep_rid,
            'unlinked':unlinked,'moved_rbl':moved,'del_rbl':del_rbl,'remap':remap_counts,
            'year':x['transaction_date'].year
        })
        cur.execute('RELEASE SAVEPOINT pair_sp')
    except Exception as e:
        cur.execute('ROLLBACK TO SAVEPOINT pair_sp')
        skipped.append({'tx_bad':tx_bad,'tx_good':tx_good,'reason':str(e)})
        cur.execute('RELEASE SAVEPOINT pair_sp')

if DRY_RUN:
    conn.rollback(); print('DRY RUN rollback')
else:
    conn.commit(); print('APPLIED commit')

print('applied_count', len(applied))
print('skipped_count', len(skipped))
print('total_unlinked_receipts', sum(a['unlinked'] for a in applied))
print('total_deleted_rbl', sum(a['del_rbl'] for a in applied))
by_year=defaultdict(int)
for a in applied: by_year[a['year']]+=1
print('applied_by_year', dict(sorted(by_year.items())))
print('sample_applied')
for a in applied[:80]:
    print(a)
if skipped:
    print('sample_skipped')
    for s in skipped[:40]:
        print(s)

# Validate residual strict pairs count
cur2=conn.cursor(cursor_factory=RealDictCursor)
cur2.execute("""
SELECT transaction_id, account_number, transaction_date, COALESCE(debit_amount,0) AS debit_amount,
       COALESCE(vendor_extracted,'') AS vendor_extracted, COALESCE(description,'') AS description,
       COALESCE(source_file,'') AS source_file, COALESCE(import_batch,'') AS import_batch
FROM banking_transactions
WHERE account_number IN ('0228362','8362','1615')
  AND COALESCE(debit_amount,0) > 0
ORDER BY transaction_date, transaction_id
""")
rows=cur2.fetchall(); a=[r for r in rows if r['account_number'] in ('0228362','8362')]; b=[r for r in rows if r['account_number']=='1615']
rem=0
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
            rem += 1
print('remaining_strict_pairs_after_apply', rem)

cur2.close(); cur.close(); conn.close()
