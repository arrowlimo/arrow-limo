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
    return sorted(receipts, key=lambda r:(is_review_receipt(r), -receipt_quality_score(r, canonical_tx), r['receipt_id']))[0]

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

# FK map
cur.execute("""
SELECT conrelid::regclass::text AS tbl, a.attname AS col
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE c.contype='f' AND c.confrelid='banking_transactions'::regclass
ORDER BY 1,2
""")
fk_targets=[(r['tbl'], r['col']) for r in cur.fetchall()]
skip_generic={('receipts','banking_transaction_id'),('receipt_banking_links','transaction_id')}
extra_targets=[x for x in fk_targets if x not in skip_generic]

# load txs
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

# remaining strict pairs
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
            # count receipts on candidate canonical
            cur.execute("SELECT COUNT(*) AS c FROM receipts WHERE banking_transaction_id=%s", (y['transaction_id'],))
            rc=cur.fetchone()['c']
            pair_score=(len(inter)*10) + (20 if exact_desc else 0) + (30 if sig else 0) + rc
            pairs.append((x,y,pair_score,len(inter),exact_desc,sig,rc))

print('remaining_pairs_input', len(pairs))

# choose best canonical 1615 per tx8362
best_for_bad={}
for x,y,ps,ov,ed,sig,rc in pairs:
    bid=x['transaction_id']
    cur_best=best_for_bad.get(bid)
    cand=(ps, ov, ed, sig, rc, -y['transaction_id'], y)
    if cur_best is None or cand>cur_best[0]:
        best_for_bad[bid]=(cand,x)

# group bad tx under chosen canonical good tx
groups=defaultdict(list)
for bid,(cand,x) in best_for_bad.items():
    y=cand[-1]
    groups[y['transaction_id']].append(x)

print('groups_count', len(groups))
print('bad_tx_count', sum(len(v) for v in groups.values()))

applied=[]
skipped=[]

for tx_good, bad_rows in groups.items():
    cur.execute('SAVEPOINT gsp')
    try:
        bad_ids=sorted({r['transaction_id'] for r in bad_rows})

        # collect receipts attached to tx_good + all bad tx
        ph=','.join(['%s']*(len(bad_ids)+1))
        params=[tx_good]+bad_ids
        cur.execute(f"""
            SELECT receipt_id, vendor_name, canonical_vendor, description, gross_amount, receipt_date,
                   banking_transaction_id, receipt_source, exclude_from_reports,
                   gl_account_code, gl_code, fuel, fuel_amount, split_key, split_group_id,
                   is_split_receipt, receipt_review_notes
            FROM receipts
            WHERE banking_transaction_id IN ({ph})
            ORDER BY receipt_id
        """, params)
        recs=cur.fetchall()

        keep_rid=None
        if recs:
            best=pick_best_receipt(recs, tx_good)
            keep_rid=best['receipt_id']
            cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s", (tx_good, keep_rid))

        unlinked=0; del_rbl=0; moved=0; remap_total=0; deleted=0
        for tx_bad in bad_ids:
            # unlink other receipts from each bad tx
            if keep_rid is not None:
                cur.execute("UPDATE receipts SET banking_transaction_id=NULL WHERE banking_transaction_id=%s AND receipt_id<>%s", (tx_bad, keep_rid))
            else:
                cur.execute("UPDATE receipts SET banking_transaction_id=NULL WHERE banking_transaction_id=%s", (tx_bad,))
            unlinked += cur.rowcount

            # move keep receipt link from bad->good if needed
            if keep_rid is not None:
                cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (keep_rid, tx_good))
                has_good=cur.fetchone()['c']>0
                cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (keep_rid, tx_bad))
                has_bad=cur.fetchone()['c']>0
                if has_bad and not has_good:
                    cur.execute("UPDATE receipt_banking_links SET transaction_id=%s WHERE receipt_id=%s AND transaction_id=%s", (tx_good, keep_rid, tx_bad))
                    moved += cur.rowcount

            cur.execute("DELETE FROM receipt_banking_links WHERE transaction_id=%s", (tx_bad,))
            del_rbl += cur.rowcount

            # remap other FK refs
            for tbl,col in extra_targets:
                q=f"UPDATE {tbl} SET {col}=%s WHERE {col}=%s"
                cur.execute(q, (tx_good, tx_bad))
                remap_total += cur.rowcount

            cur.execute("DELETE FROM banking_transactions WHERE transaction_id=%s", (tx_bad,))
            if cur.rowcount!=1:
                raise Exception(f'delete_failed_{tx_bad}')
            deleted += 1

        if keep_rid is not None:
            cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s", (keep_rid, tx_good))

        applied.append({'tx_good':tx_good,'bad_deleted':deleted,'keep_rid':keep_rid,'unlinked':unlinked,'del_rbl':del_rbl,'moved_rbl':moved,'fk_remaps':remap_total})
        cur.execute('RELEASE SAVEPOINT gsp')
    except Exception as e:
        cur.execute('ROLLBACK TO SAVEPOINT gsp')
        skipped.append({'tx_good':tx_good,'bad_ids':[r['transaction_id'] for r in bad_rows],'reason':str(e)})
        cur.execute('RELEASE SAVEPOINT gsp')

if DRY_RUN:
    conn.rollback(); print('DRY RUN rollback')
else:
    conn.commit(); print('APPLIED commit')

print('groups_applied', len(applied))
print('groups_skipped', len(skipped))
print('bad_rows_deleted', sum(a['bad_deleted'] for a in applied))
print('unlinked_receipts', sum(a['unlinked'] for a in applied))
print('deleted_rbl', sum(a['del_rbl'] for a in applied))
print('fk_remaps', sum(a['fk_remaps'] for a in applied))
print('sample_applied')
for a in applied[:80]:
    print(a)
if skipped:
    print('sample_skipped')
    for s in skipped[:20]:
        print(s)

# post-validate
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
        if abs((x['transaction_date']-y['transaction_date']).days)!=0: continue
        inter=xt & norm_tokens(y['vendor_extracted']+' '+y['description'])
        exact_desc=(x['description'].strip().upper()==y['description'].strip().upper())
        strong=sig or exact_desc or (len(inter)>=2)
        risky=any(k in (x['description']+' '+y['description']).upper() for k in ['WITHDRAWAL','ABM','ATM','CASH'])
        if strong and not (risky and not sig): rem += 1
print('remaining_strict_pairs_after_group_pass', rem)

cur2.close(); cur.close(); conn.close()
