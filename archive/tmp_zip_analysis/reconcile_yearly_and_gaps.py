import zipfile, xml.etree.ElementTree as ET, re
from collections import Counter, defaultdict
from datetime import datetime
import psycopg2
from psycopg2 import sql

ZIP_PATH = r"L:\CRAauditexport__2002-01-01_2025-12-31__20251019T204151.zip"
DB = dict(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
TOP = ['unified_general_ledger','banking_transactions','vendor_invoices','receipts','general_ledger']

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

cra_pairs=Counter(); cra_year=defaultdict(float); cra_rows=0
with zipfile.ZipFile(ZIP_PATH) as z:
    tx=[n for n in z.namelist() if n.lower().endswith('transactions.xml')][0]
    with z.open(tx) as f:
        for _,e in ET.iterparse(f,events=('end',)):
            if strip_ns(e.tag)!='DataRow': continue
            row={strip_ns(c.tag).lower():(c.text or '').strip() for c in list(e)}
            d=parse_date(row.get('tx_date') or row.get('date') or row.get('create_date'))
            a=parse_num(row.get('amount') or row.get('tx_amount') or row.get('debit') or row.get('credit'))
            cra_rows+=1
            if d and a is not None:
                cra_pairs[(d,round(abs(a),2))]+=1
                cra_year[d.year]+=a
            e.clear()

conn=psycopg2.connect(**DB); conn.autocommit=True; cur=conn.cursor()
print("SQL[yearly_totals_template]=SELECT EXTRACT(YEAR FROM {dcol})::int AS yr, round(sum({amount_expr})::numeric,2) AS amt FROM public.{table} WHERE {dcol} IS NOT NULL GROUP BY 1 ORDER BY 1;")
print("SQL[pair_coverage_template]=SELECT {dcol}::date, abs({amount_expr}::numeric) FROM public.{table} WHERE {dcol} IS NOT NULL AND {amount_expr} IS NOT NULL;")

for t in TOP:
    cur.execute("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",(t,))
    cols=cur.fetchall(); names=[c for c,_ in cols]
    date_cols=[c for c,d in cols if d in ('date','timestamp without time zone','timestamp with time zone')]
    if not date_cols:
        print(f"table={t} skipped=no_date_col")
        continue
    dcol=date_cols[0]
    if 'debit_amount' in names and 'credit_amount' in names:
        amount_expr='COALESCE(debit_amount,0)-COALESCE(credit_amount,0)'
    elif 'debit' in names and 'credit' in names:
        amount_expr='COALESCE(debit,0)-COALESCE(credit,0)'
    elif 'amount' in names:
        amount_expr='amount'
    elif 'invoice_amount' in names:
        amount_expr='invoice_amount'
    elif 'gross_amount' in names:
        amount_expr='gross_amount'
    else:
        num=[c for c,d in cols if d in ('numeric','double precision','real','integer','bigint','smallint','decimal') and any(k in c.lower() for k in ['amount','total','debit','credit','paid','balance'])]
        if not num:
            print(f"table={t} skipped=no_amount_col")
            continue
        amount_expr=num[0]

    qy=f'SELECT EXTRACT(YEAR FROM "{dcol}")::int AS yr, round(sum({amount_expr})::numeric,2) AS amt FROM public."{t}" WHERE "{dcol}" IS NOT NULL GROUP BY 1 ORDER BY 1'
    cur.execute(qy)
    db_year={int(y):float(a) for y,a in cur.fetchall()}
    years=sorted(set(cra_year)|set(db_year))
    diffs=[(y, round(cra_year.get(y,0)-db_year.get(y,0),2)) for y in years]
    nonzero=[x for x in diffs if abs(x[1])>0.01]

    qp=f'SELECT "{dcol}"::date, abs(({amount_expr})::numeric) FROM public."{t}" WHERE "{dcol}" IS NOT NULL AND ({amount_expr}) IS NOT NULL'
    cur.execute(qp)
    db_pairs=Counter((r[0],round(float(r[1]),2)) for r in cur.fetchall())
    matched=sum(min(v,db_pairs.get(k,0)) for k,v in cra_pairs.items())
    cov=matched/cra_rows*100 if cra_rows else 0

    # missing date bands summary from pair multiset diff
    miss_by_year=defaultdict(int)
    for (d,a),n in cra_pairs.items():
        m=db_pairs.get((d,a),0)
        if n>m: miss_by_year[d.year]+= (n-m)
    top_miss=sorted(miss_by_year.items(), key=lambda x:-x[1])[:6]

    print(f"table={t} dcol={dcol} amount_expr={amount_expr} pair_cov={cov:.2f} unmatched_rows={cra_rows-matched} nonzero_year_diffs={len(nonzero)} top_year_diff_sample={nonzero[:6]} top_missing_years={top_miss}")

cur.close(); conn.close()
