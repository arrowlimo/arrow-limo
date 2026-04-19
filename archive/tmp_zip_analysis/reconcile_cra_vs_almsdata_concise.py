import zipfile, xml.etree.ElementTree as ET, re
from collections import Counter, defaultdict
from datetime import datetime
import psycopg2
from psycopg2 import sql

ZIP_PATH = r"L:\CRAauditexport__2002-01-01_2025-12-31__20251019T204151.zip"
DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

SQL_CANDIDATES = """
SELECT t.table_name
FROM information_schema.tables t
WHERE t.table_schema='public'
  AND t.table_type='BASE TABLE'
  AND (
      t.table_name IN ('general_ledger','banking_transactions','receipts','charter_payments','payments','vendor_invoices')
      OR t.table_name ILIKE 'gl_%'
      OR t.table_name ILIKE '%ledger%'
      OR t.table_name ILIKE '%transaction%'
      OR t.table_name ILIKE '%receipt%'
      OR t.table_name ILIKE '%payment%'
      OR t.table_name ILIKE '%invoice%'
  )
ORDER BY t.table_name;
""".strip()
SQL_COLS = "SELECT c.column_name, c.data_type FROM information_schema.columns c WHERE c.table_schema='public' AND c.table_name=%s ORDER BY c.ordinal_position;"


def strip_ns(tag): return tag.split('}',1)[1] if '}' in tag else tag

def parse_num(s):
    if s is None: return None
    t=str(s).strip().replace(',','')
    if not t:return None
    if t.startswith('(') and t.endswith(')'): t='-'+t[1:-1]
    try:return float(t)
    except:return None

def parse_date(s):
    if not s:return None
    s=s.strip()
    for f in ['%Y-%m-%d','%Y/%m/%d','%m/%d/%Y','%Y-%m-%d %H:%M:%S','%Y-%m-%dT%H:%M:%S']:
        try:return datetime.strptime(s[:19],f).date()
        except:pass
    m=re.match(r'^(\d{4}-\d{2}-\d{2})',s)
    if m:
        try:return datetime.strptime(m.group(1),'%Y-%m-%d').date()
        except:pass
    return None

cra_rows=0; cra_dates=[]; cra_pairs=Counter(); cra_year=defaultdict(float); cra_txn=set(); cra_seq=set(); colset=set()
with zipfile.ZipFile(ZIP_PATH) as z:
    tx=[n for n in z.namelist() if n.lower().endswith('transactions.xml')][0]
    with z.open(tx) as f:
        for _,e in ET.iterparse(f,events=('end',)):
            if strip_ns(e.tag)!='DataRow': continue
            row={strip_ns(c.tag).lower():(c.text or '').strip() for c in list(e)}
            cra_rows+=1; colset.update(row.keys())
            d=parse_date(row.get('tx_date') or row.get('date') or row.get('create_date'))
            a=parse_num(row.get('amount') or row.get('tx_amount') or row.get('debit') or row.get('credit'))
            if d: cra_dates.append(d)
            if d and a is not None:
                cra_pairs[(d,round(abs(a),2))]+=1
                cra_year[d.year]+=a
            if row.get('txn_id'): cra_txn.add(row['txn_id'])
            if row.get('sequence'): cra_seq.add(row['sequence'])
            e.clear()

conn=psycopg2.connect(**DB); conn.autocommit=True; cur=conn.cursor()
cur.execute(SQL_CANDIDATES); tables=[r[0] for r in cur.fetchall()]
res=[]
for t in tables:
    cur.execute(SQL_COLS,(t,)); cols=cur.fetchall()
    typed_date=[c for c,d in cols if d in ('date','timestamp without time zone','timestamp with time zone')]
    amount=[c for c,d in cols if any(k in c.lower() for k in ['amount','total','debit','credit','paid','balance']) and d in ('numeric','double precision','real','integer','bigint','smallint','decimal')]
    ext=[c for c,d in cols if any(k in c.lower() for k in ['txn_id','transaction_id','external','sequence','reference_no','ref_no','bank_id'])]
    dcol=typed_date[0] if typed_date else None
    acol=amount[0] if amount else None
    cur.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(t))); rc=cur.fetchone()[0]
    dmin=dmax=None
    if dcol:
        cur.execute(sql.SQL('SELECT min({})::date,max({})::date FROM public.{}').format(sql.Identifier(dcol),sql.Identifier(dcol),sql.Identifier(t))); dmin,dmax=cur.fetchone()
    best_match=0; best_col=None; basis=None; denom=0
    for k in ext:
        cur.execute(sql.SQL('SELECT {}::text FROM public.{} WHERE {} IS NOT NULL').format(sql.Identifier(k),sql.Identifier(t),sql.Identifier(k)))
        vals=set(v[0].strip() for v in cur.fetchall() if v[0] and v[0].strip())
        mt=len(vals&cra_txn); ms=len(vals&cra_seq)
        if mt>=ms: m,b,den=mt,'txn_id',len(cra_txn)
        else: m,b,den=ms,'sequence',len(cra_seq)
        if m>best_match: best_match,best_col,basis,denom=m,k,b,den
    cov=None
    if dcol and acol:
        cur.execute(sql.SQL('SELECT {}::date, abs({}::numeric) FROM public.{} WHERE {} IS NOT NULL AND {} IS NOT NULL').format(sql.Identifier(dcol),sql.Identifier(acol),sql.Identifier(t),sql.Identifier(dcol),sql.Identifier(acol)))
        dbpairs=Counter((r[0],round(float(r[1]),2)) for r in cur.fetchall())
        matched=sum(min(v,dbpairs.get(k,0)) for k,v in cra_pairs.items())
        cov=matched/cra_rows*100 if cra_rows else None
    res.append((t,rc,dcol,acol,dmin,dmax,best_col,basis,best_match,denom,cov))
cur.close(); conn.close()
res=sorted(res,key=lambda x:(0 if x[8]>0 else 1,-x[8],-(x[10] or 0),-x[1]))

print('SQL[candidate_tables]='+SQL_CANDIDATES.replace('\n',' '))
print('SQL[table_columns]='+SQL_COLS)
print('SQL[row_count]=SELECT count(*) FROM public.{table};')
print('SQL[date_min_max]=SELECT min({dcol})::date,max({dcol})::date FROM public.{table};')
print('SQL[pair_pull]=SELECT {dcol}::date, abs({acol}::numeric) FROM public.{table} WHERE {dcol} IS NOT NULL AND {acol} IS NOT NULL;')
print('SQL[ext_key_pull]=SELECT {kcol}::text FROM public.{table} WHERE {kcol} IS NOT NULL;')
print(f'CRA rows={cra_rows} columns={len(colset)} date_min={min(cra_dates) if cra_dates else None} date_max={max(cra_dates) if cra_dates else None} txn_id_distinct={len(cra_txn)} sequence_distinct={len(cra_seq)}')
print(f'candidate_table_count={len(tables)}')
for r in res[:12]:
    print(f'table={r[0]} rows={r[1]} date_col={r[2]} amount_col={r[3]} dmin={r[4]} dmax={r[5]} key={r[6]} basis={r[7]} key_match={r[8]}/{r[9]} pair_cov={None if r[10] is None else round(r[10],2)}')
if res:
    b=res[0]
    cov=b[10] or 0.0
    print(f'best_table={b[0]} key_match={b[8]}/{b[9]} pair_cov={round(cov,2)} estimated_missing_rows={max(0,int(round(cra_rows*(1-cov/100))))}')
