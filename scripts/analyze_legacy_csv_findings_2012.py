import os, csv, json, re
from pathlib import Path

SRC = Path('exports/docs/legacy_xls_csv')
OUT = SRC / 'findings_2012.md'

NUM_COLS = ['amount','debit','credit','total','gross','net']


def to_float(s):
    try:
        return float(str(s).replace(',',''))
    except Exception:
        return 0.0


def sum_numeric_cols(path: Path):
    sums = {}
    with path.open('r', encoding='utf-8', newline='') as f:
        r = csv.DictReader(f)
        cols = [c.lower() for c in r.fieldnames or []]
        idx = {c.lower(): c for c in (r.fieldnames or [])}
        cand = [idx[c] for c in cols if any(nc in c for nc in NUM_COLS)]
        for row in r:
            for c in cand:
                sums[c] = sums.get(c, 0.0) + to_float(row.get(c))
    return sums


def main():
    files = list(SRC.glob('*.csv'))
    lines = ['# Legacy XLS CSV findings for 2012', '']

    # Accounts Payable 2012 overview
    ap_files = [f for f in files if f.name.startswith('Accounts Payable Workbook 2012')]
    if ap_files:
        lines.append('## Accounts Payable Workbook 2012 (totals by numeric columns)')
        for f in ap_files:
            sums = sum_numeric_cols(f)
            total = sum(v for v in sums.values())
            lines.append(f"- {f.name}: sum(all numeric cols) = ${total:,.2f}")
        lines.append('')

    # Payroll coverage: list months present
    ytd = [f for f in files if f.name.startswith('2012 YTD Hourly Payroll Workbook')]
    months = set()
    for f in ytd:
        m = re.search(r'_(\w{3})_12', f.stem)
        if m:
            months.add(m.group(1))
    if months:
        lines.append('## 2012 YTD Hourly Payroll Workbook months present')
        lines.append('- ' + ', '.join(sorted(months)))
        lines.append('')

    # Scotiabank checks listing
    chk = SRC / 'Scotiabank checks 1 through 0124_Sheet1.csv'
    if chk.exists():
        lines.append('## Scotiabank checks 1-124 (first 20 rows)')
        with chk.open('r', encoding='utf-8', newline='') as f:
            r = csv.reader(f)
            head = next(r, [])
            lines.append('- Header: ' + ', '.join(head))
            for i, row in enumerate(r):
                if i >= 20:
                    break
                lines.append('  - ' + ' | '.join(row))
        lines.append('')

    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print({'written': str(OUT)})

if __name__ == '__main__':
    main()
