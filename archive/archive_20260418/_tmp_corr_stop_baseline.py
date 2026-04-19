import csv
from pathlib import Path
import psycopg2

src = Path(r'l:\limo\data\audit\nsf_correction_high_conf_candidates_20260407_190606.csv')
if not src.exists():
    raise SystemExit('source csv missing')

corr_ids = []
with src.open(newline='', encoding='utf-8') as f:
    r = csv.DictReader(f)
    for row in r:
        reason = (row.get('reason') or '')
        suggest_excl = (row.get('suggest_set_exclude_from_reports') or '').lower() == 'true'
        suggest_nsf = (row.get('suggest_set_is_nsf') or '').lower() == 'true'
        if suggest_excl and (('keyword_correction' in reason) or ('keyword_stop_payment' in reason)) and not suggest_nsf:
            corr_ids.append(int(row['receipt_id']))

corr_ids = sorted(set(corr_ids))
print('corr_stop_candidate_ids', len(corr_ids))

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM receipts WHERE receipt_id = ANY(%s) AND COALESCE(exclude_from_reports,false)=false', (corr_ids,))
print('before_unexcluded_in_candidates', cur.fetchone()[0])
cur.close(); conn.close()
