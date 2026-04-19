import zipfile, xml.etree.ElementTree as ET, re
from collections import Counter, defaultdict
from datetime import datetime
import psycopg2
from psycopg2 import sql

ZIP_PATH = r"L:\CRAauditexport__2002-01-01_2025-12-31__20251019T204151.zip"
DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

SQL_SNIPPETS = {
    "candidate_tables": """
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
""".strip(),
    "table_columns": """
SELECT c.column_name, c.data_type
FROM information_schema.columns c
WHERE c.table_schema='public' AND c.table_name=%s
ORDER BY c.ordinal_position;
""".strip(),
    "row_count": "SELECT count(*) FROM public.{table};",
    "date_min_max": "SELECT min({dcol})::text, max({dcol})::text FROM public.{table};",
    "yearly_totals": "SELECT EXTRACT(YEAR FROM {dcol})::int AS yr, round(sum({acol})::numeric,2) AS amt FROM public.{table} WHERE {dcol} IS NOT NULL AND {acol} IS NOT NULL GROUP BY 1 ORDER BY 1;",
    "pair_pull": "SELECT {dcol}::date AS d, abs({acol}::numeric) AS a FROM public.{table} WHERE {dcol} IS NOT NULL AND {acol} IS NOT NULL;",
    "ext_key_pull": "SELECT {kcol}::text FROM public.{table} WHERE {kcol} IS NOT NULL;"
}

def strip_ns(tag):
    return tag.split('}',1)[1] if '}' in tag else tag

def parse_num(s):
    if s is None: return None
    t = str(s).strip().replace(',','')
    if not t: return None
    if t.startswith('(') and t.endswith(')'):
        t = '-' + t[1:-1]
    try: return float(t)
    except: return None

def parse_date(s):
    if not s: return None
    s = s.strip()
    for f in ['%Y-%m-%d','%Y/%m/%d','%m/%d/%Y','%Y-%m-%d %H:%M:%S','%Y-%m-%dT%H:%M:%S']:
        try: return datetime.strptime(s[:19], f).date()
        except: pass
    m = re.match(r'^(\d{4}-\d{2}-\d{2})', s)
    if m:
        try: return datetime.strptime(m.group(1),'%Y-%m-%d').date()
        except: pass
    return None

def find_transactions_xml(z):
    for n in z.namelist():
        if n.lower().endswith('transactions.xml'): return n
    raise RuntimeError('Transactions.xml not found')

# CRA parse
cra_rows = 0
col_counter = Counter()
cra_dates = []
cra_txn_ids = set(); cra_sequences = set()
cra_pairs = Counter(); cra_year_totals = defaultdict(float)

with zipfile.ZipFile(ZIP_PATH) as z:
    m = find_transactions_xml(z)
    with z.open(m) as f:
        for _,e in ET.iterparse(f, events=('end',)):
            if strip_ns(e.tag) != 'DataRow':
                continue
            row = {strip_ns(c.tag).strip().lower(): (c.text or '').strip() for c in list(e)}
            cra_rows += 1
            col_counter.update(row.keys())
            d = parse_date(row.get('tx_date') or row.get('date') or row.get('create_date'))
            a = parse_num(row.get('amount') or row.get('tx_amount') or row.get('debit') or row.get('credit'))
            if d: cra_dates.append(d)
            if d and a is not None:
                cra_pairs[(d, round(abs(a),2))] += 1
                cra_year_totals[d.year] += a
            tx = (row.get('txn_id') or '').strip(); seq = (row.get('sequence') or '').strip()
            if tx: cra_txn_ids.add(tx)
            if seq: cra_sequences.add(seq)
            e.clear()

cra_cols = sorted(col_counter)
cra_date_min = min(cra_dates).isoformat() if cra_dates else None
cra_date_max = max(cra_dates).isoformat() if cra_dates else None

conn = psycopg2.connect(**DB); conn.autocommit = True; cur = conn.cursor()
cur.execute(SQL_SNIPPETS['candidate_tables']); candidates = [r[0] for r in cur.fetchall()]

results = []
for t in candidates:
    cur.execute(SQL_SNIPPETS['table_columns'], (t,)); cols = cur.fetchall()
    # strict date-typed first; then safe name-based excluding obvious non-date numeric metrics
    typed_date = [c for c,dt in cols if dt in ('date','timestamp without time zone','timestamp with time zone')]
    named_date = [c for c,dt in cols if ('date' in c.lower()) and not any(x in c.lower() for x in ['difference','age','days']) and dt not in ('integer','bigint','smallint','numeric','double precision','real')]
    date_cols = typed_date + [c for c in named_date if c not in typed_date]
    amount_cols = [c for c,dt in cols if any(k in c.lower() for k in ['amount','total','debit','credit','paid','balance']) and dt in ('numeric','double precision','real','integer','bigint','smallint','decimal')]
    desc_ref_cols = [c for c,dt in cols if any(k in c.lower() for k in ['desc','memo','note','ref','reference','details','name'])]
    ext_key_cols = [c for c,dt in cols if any(k in c.lower() for k in ['txn_id','transaction_id','external','sequence','reference_no','ref_no','bank_id'])]

    cur.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(t))); row_count = cur.fetchone()[0]

    dcol = date_cols[0] if date_cols else None
    acol = amount_cols[0] if amount_cols else None
    dmin=dmax=None
    if dcol:
        try:
            q = sql.SQL('SELECT min({})::text, max({})::text FROM public.{}').format(sql.Identifier(dcol), sql.Identifier(dcol), sql.Identifier(t))
            cur.execute(q); dmin,dmax = cur.fetchone()
        except Exception:
            dcol = None

    best_key= None; best_key_match=0; best_key_total=0; key_basis=None
    for kcol in ext_key_cols:
        try:
            q = sql.SQL('SELECT {}::text FROM public.{} WHERE {} IS NOT NULL').format(sql.Identifier(kcol), sql.Identifier(t), sql.Identifier(kcol))
            cur.execute(q)
            vals = set(str(r[0]).strip() for r in cur.fetchall() if r[0] is not None and str(r[0]).strip())
            if not vals: continue
            m_txn = len(vals & cra_txn_ids); m_seq = len(vals & cra_sequences)
            if m_txn >= m_seq:
                m,den,basis = m_txn, (len(cra_txn_ids) or 0), 'txn_id'
            else:
                m,den,basis = m_seq, (len(cra_sequences) or 0), 'sequence'
            if m > best_key_match:
                best_key, best_key_match, best_key_total, key_basis = kcol, m, den, basis
        except Exception:
            continue

    pair_cov=None; yearly_diff=None; db_year_totals={}
    if dcol and acol:
        try:
            q = sql.SQL('SELECT {}::date, abs({}::numeric) FROM public.{} WHERE {} IS NOT NULL AND {} IS NOT NULL').format(sql.Identifier(dcol), sql.Identifier(acol), sql.Identifier(t), sql.Identifier(dcol), sql.Identifier(acol))
            cur.execute(q)
            db_pairs = Counter((r[0], round(float(r[1]),2)) for r in cur.fetchall() if r[0] is not None and r[1] is not None)
            matched = sum(min(v, db_pairs.get(k,0)) for k,v in cra_pairs.items())
            pair_cov = (matched / cra_rows * 100.0) if cra_rows else None

            qy = sql.SQL('SELECT EXTRACT(YEAR FROM {})::int, round(sum({})::numeric,2) FROM public.{} WHERE {} IS NOT NULL AND {} IS NOT NULL GROUP BY 1 ORDER BY 1').format(sql.Identifier(dcol), sql.Identifier(acol), sql.Identifier(t), sql.Identifier(dcol), sql.Identifier(acol))
            cur.execute(qy)
            db_year_totals = {int(y): float(a) for y,a in cur.fetchall()}
            years = sorted(set(cra_year_totals) | set(db_year_totals))
            yearly_diff = {y: round(cra_year_totals.get(y,0.0)-db_year_totals.get(y,0.0),2) for y in years}
        except Exception:
            pair_cov=None; yearly_diff=None

    results.append(dict(table=t,row_count=row_count,date_col=dcol,amount_col=acol,dmin=dmin,dmax=dmax,desc_ref_cols=desc_ref_cols[:8],ext_key_cols=ext_key_cols,best_key=best_key,best_key_match=best_key_match,best_key_total=best_key_total,key_basis=key_basis,pair_cov=pair_cov,yearly_diff=yearly_diff))

cur.close(); conn.close()
ranked = sorted(results, key=lambda r:(0 if r['best_key_match']>0 else 1, -(r['best_key_match'] or 0), -((r['pair_cov'] or 0.0)), -r['row_count']))

print('===SQL_SNIPPETS_USED===')
for k,v in SQL_SNIPPETS.items(): print(f'[{k}] {v}')
print('===CRA_PROFILE===')
print(f'rows={cra_rows} columns={len(cra_cols)} date_min={cra_date_min} date_max={cra_date_max} txn_id_distinct={len(cra_txn_ids)} sequence_distinct={len(cra_sequences)}')
print('columns=' + ','.join(cra_cols))
print('===CANDIDATE_TABLES===')
print(','.join(candidates))
print('===TABLE_METRICS===')
for r in ranked:
    print(f"table={r['table']} rows={r['row_count']} date_col={r['date_col']} amount_col={r['amount_col']} dmin={r['dmin']} dmax={r['dmax']} best_key={r['best_key']} basis={r['key_basis']} key_match={r['best_key_match']}/{r['best_key_total']} pair_cov={None if r['pair_cov'] is None else round(r['pair_cov'],2)} ext_keys={r['ext_key_cols']} desc_ref_cols={r['desc_ref_cols']}")
print('===YEARLY_DIFF_TOP3===')
for r in ranked[:3]:
    yd = r['yearly_diff']
    if not yd: continue
    nz = [(y,d) for y,d in yd.items() if abs(d)>0.01]
    print(f"table={r['table']} nonzero_years={len(nz)} sample={nz[:10]}")
print('===DECISION===')
if ranked:
    b = ranked[0]
    if b['best_key_total']:
        pct = b['best_key_match']/b['best_key_total']*100
        print(f"best_table={b['table']} key_coverage_pct={pct:.2f}")
    else:
        print(f"best_table={b['table']} pair_coverage_pct={0.0 if b['pair_cov'] is None else round(b['pair_cov'],2)}")
    cov = b['pair_cov'] if b['pair_cov'] else 0.0
    print(f"estimated_missing_rows={max(0,int(round(cra_rows*(1-cov/100.0))))} cra_date_band={cra_date_min}..{cra_date_max}")
