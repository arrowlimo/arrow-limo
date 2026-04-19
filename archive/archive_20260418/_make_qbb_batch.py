import re
from pathlib import Path
import pandas as pd

docs = Path('docs')
files = [p for p in docs.glob('*') if p.is_file() and re.search('batch', p.name, re.I) and re.search('(qbb|recon)', p.name, re.I) and p.suffix.lower() in ['.csv', '.xlsx', '.xls']]
files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
print('LATEST_BATCH=' + (str(files[0].resolve()) if files else 'NONE'))

source = docs / '2012_qbb_recon_allcols_20260417.xlsx'
sheet = 'QBB_CIBC_2012'
df = pd.read_excel(source, sheet_name=sheet, dtype=str)
df.columns = [str(c).strip() for c in df.columns]

wanted = ['page', 'type', 'date', 'ref', 'payee', 'cleared', 'amount', 'balance']
lower = {c.lower(): c for c in df.columns}
missing = [c for c in wanted if c not in lower]
if missing:
    raise SystemExit('Missing columns: ' + ','.join(missing))

out = df[[lower[c] for c in wanted]].copy()
out.columns = wanted
out = out.fillna('')
for c in wanted:
    out[c] = out[c].astype(str).str.strip()

prior_keys = set()
for p in files:
    if p.suffix.lower() == '.csv':
        try:
            b = pd.read_csv(p, dtype=str).fillna('')
            b.columns = [str(c).strip().lower() for c in b.columns]
            if all(k in b.columns for k in ['date', 'ref', 'payee', 'amount']):
                for row in b[['date', 'ref', 'payee', 'amount']].astype(str).itertuples(index=False, name=None):
                    prior_keys.add(tuple(x.strip() for x in row))
        except Exception:
            pass

keys = [tuple(x.strip() for x in row) for row in out[['date', 'ref', 'payee', 'amount']].astype(str).itertuples(index=False, name=None)]
out = out[[k not in prior_keys for k in keys]].copy()

out['_prio'] = out['cleared'].str.upper().eq('X').map({True: 0, False: 1})
out['_ord'] = range(len(out))
out = out.sort_values(['_prio', '_ord']).drop(columns=['_prio', '_ord'])
out = out.head(200)

nums = []
for p in files:
    m = re.search(r'(?i)batch[_-]?(\d+)', p.stem)
    if m:
        nums.append(int(m.group(1)))
next_num = (max(nums) + 1) if nums else 1
fname = f"2012_qbb_recon_batch_{next_num:03d}_{pd.Timestamp.today().strftime('%Y%m%d')}.csv"
target = docs / fname
out.to_csv(target, index=False, encoding='utf-8')

print('OUTPUT_FILE=' + str(target.resolve()))
print('ROW_COUNT=' + str(len(out)))
print('FIRST5')
print(out.head(5).to_csv(index=False).strip())
