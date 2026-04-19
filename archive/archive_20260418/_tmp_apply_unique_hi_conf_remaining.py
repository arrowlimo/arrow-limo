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
    src=(r.get('receipt_source') or '').lower(); vendor=(r.get('vendor_name') or '').upper()
    return ('unlinked' in vendor) or ('review' in vendor) or src.startswith('auto_') or bool(r.get('exclude_from_reports'))

def score_receipt(r, good):
    s=0
    if r.get('canonical_vendor'): s+=20
    if r.get('gl_account_code') or r.get('gl_code'): s+=30
    if r.get('is_split_receipt') or r.get('split_key') or r.get('split_group_id'): s+=15
    if r.get('fuel') or (r.get('fuel_amount') or 0)>0: s+=10
    if not r.get('exclude_from_reports'): s+=8
    if r.get('banking_transaction_id')==good: s+=5
    if is_review_receipt(r): s-=120
    return s

def pick_best(rs, good):
    return sorted(rs, key=lambda r:(is_review_receipt(r), -score_receipt(r,good), r['receipt_id']))[0]

conn=psycopg2.connect(dbname='almsdata', user='postgres', password='ArrowLimousine', host='localhost', port=5432)
conn.autocommit=False
cur=conn.cursor(cursor_factory=RealDictCursor)

# FK tables
cur.execute("""
SELECT conrelid::regclass::text AS tbl, a.attname AS col
FROM pg_constraint c
JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
WHERE c.contype='f' AND c.confrelid='banking_transactions'::regclass
ORDER BY 1,2
""")
all_fk=[(r['tbl'], r['col']) for r in cur.fetchall()]
extra=[x for x in all_fk if x not in {('receipts','banking_transaction_id'),('receipt_banking_links','transaction_id')}]

cur.execute("""
SELECT transaction_id, account_number, transaction_date, COALESCE(debit_amount,0) AS debit_amount,
       COALESCE(vendor_extracted,'') AS vendor_extracted, COALESCE(description,'') AS description
FROM banking_transactions
WHERE account_number IN ('0228362','8362','1615') AND COALESCE(debit_amount,0)>0
ORDER BY transaction_date, transaction_id
""")
rows=cur.fetchall(); a=[r for r in rows if r['account_number'] in ('0228362','8362')]; b=[r for r in rows if r['account_number']=='1615']

cand=defaultdict(list)
for x in a:
    xt=norm_tokens(x['vendor_extracted']+' '+x['description'])
    for y in b:
        if abs(Decimal(x['debit_amount'])-Decimal(y['debit_amount']))>=Decimal('0.01'): continue
        dd=abs((x['transaction_date']-y['transaction_date']).days)
        if dd>3: continue
        ov=len(xt & norm_tokens(y['vendor_extracted']+' '+y['description']))
        if ov<2: continue
        cand[x['transaction_id']].append((y,dd,ov))

# only unique candidate tx8362 rows
pairs=[]
for bad_id,lst in cand.items():
    # keep only best by day gap then overlap desc
    lst=sorted(lst, key=lambda t:(t[1], -t[2], t[0]['transaction_id']))
    # unique if next isn't tied on key and no same good id duplicates
    if len(lst)>1 and (lst[1][1],lst[1][2])==(lst[0][1],lst[0][2]):
        continue
    good=lst[0][0]
    # find bad row object
    bad=next(r for r in a if r['transaction_id']==bad_id)
    pairs.append((bad,good))

print('unique_high_conf_pairs_to_apply', len(pairs))

applied=[]
for bad,good in pairs:
    tx_bad=bad['transaction_id']; tx_good=good['transaction_id']
    cur.execute('SAVEPOINT sp')
    try:
        cur.execute("""
        SELECT receipt_id, vendor_name, canonical_vendor, description, banking_transaction_id,
               receipt_source, exclude_from_reports, gl_account_code, gl_code,
               fuel, fuel_amount, split_key, split_group_id, is_split_receipt
        FROM receipts WHERE banking_transaction_id IN (%s,%s) ORDER BY receipt_id
        """, (tx_bad, tx_good))
        rs=cur.fetchall()
        keep=None
        if rs:
            keep=pick_best(rs, tx_good)['receipt_id']
            cur.execute("UPDATE receipts SET banking_transaction_id=%s WHERE receipt_id=%s", (tx_good, keep))
            cur.execute("UPDATE receipts SET banking_transaction_id=NULL WHERE banking_transaction_id=%s AND receipt_id<>%s", (tx_bad, keep))
            unlinked=cur.rowcount
        else:
            unlinked=0

        if keep is not None:
            cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (keep,tx_good)); hasg=cur.fetchone()['c']>0
            cur.execute("SELECT COUNT(*) AS c FROM receipt_banking_links WHERE receipt_id=%s AND transaction_id=%s", (keep,tx_bad)); hasb=cur.fetchone()['c']>0
            if hasb and not hasg:
                cur.execute("UPDATE receipt_banking_links SET transaction_id=%s WHERE receipt_id=%s AND transaction_id=%s", (tx_good,keep,tx_bad))
        cur.execute("DELETE FROM receipt_banking_links WHERE transaction_id=%s", (tx_bad,)); delrbl=cur.rowcount

        for tbl,col in extra:
            q=f"UPDATE {tbl} SET {col}=%s WHERE {col}=%s"
            cur.execute(q, (tx_good, tx_bad))
        if keep is not None:
            cur.execute("UPDATE banking_transactions SET receipt_id=%s WHERE transaction_id=%s", (keep, tx_good))
        cur.execute("DELETE FROM banking_transactions WHERE transaction_id=%s", (tx_bad,))
        if cur.rowcount!=1: raise Exception('delete failed')

        applied.append((tx_bad,tx_good,keep,unlinked,delrbl,bad['transaction_date'].year,float(bad['debit_amount'])))
        cur.execute('RELEASE SAVEPOINT sp')
    except Exception:
        cur.execute('ROLLBACK TO SAVEPOINT sp'); cur.execute('RELEASE SAVEPOINT sp')

if DRY_RUN: conn.rollback(); print('rollback')
else: conn.commit(); print('commit')

print('applied_count', len(applied))
for arow in applied:
    print({'tx8362_deleted':arow[0],'tx1615_kept':arow[1],'keep_receipt':arow[2],'unlinked':arow[3],'del_rbl':arow[4],'year':arow[5],'amt':arow[6]})

cur.close(); conn.close()
