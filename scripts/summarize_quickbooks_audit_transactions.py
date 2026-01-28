"""
Scan QuickBooks CRA audit export ZIPs and summarize transaction year coverage.

Looks for files like: quickbooks/CRAauditexport__2002-01-01_2025-12-31__*.zip
Reads Transactions.xml inside each ZIP and extracts years from date-like strings.

Output: reports/quickbooks_audit_transactions_years.md
"""
from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile
from collections import Counter, defaultdict


ROOT = Path('l:/limo')
QB_DIR = ROOT / 'quickbooks'
OUT = ROOT / 'reports' / 'quickbooks_audit_transactions_years.md'

DATE_PATTERN = re.compile(r'(\d{4})[-/](\d{2})[-/](\d{2})')


def extract_years_from_zip(zip_path: Path) -> Counter:
    years = Counter()
    try:
        with ZipFile(zip_path) as zf:
            # Prefer Transactions.xml but scan any *.xml if not present
            names = zf.namelist()
            candidates = [n for n in names if n.lower().endswith('transactions.xml')]
            if not candidates:
                candidates = [n for n in names if n.lower().endswith('.xml')]
            for name in candidates:
                with zf.open(name, 'r') as f:
                    for raw in f:
                        try:
                            line = raw.decode('utf-8', errors='ignore')
                        except Exception:
                            continue
                        for m in DATE_PATTERN.finditer(line):
                            yr = int(m.group(1))
                            if 1900 <= yr <= 2100:
                                years[yr] += 1
            return years
    except Exception:
        return years


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    zips = sorted(QB_DIR.glob('CRAauditexport__*_*.zip'))
    if not zips:
        OUT.write_text('# QuickBooks Audit Transactions - No ZIPs found\n')
        print(f'No CRA audit export ZIPs found in {QB_DIR}')
        return

    per_zip = {}
    global_years = Counter()
    for zp in zips:
        yrs = extract_years_from_zip(zp)
        per_zip[zp.name] = yrs
        global_years.update(yrs)

    lines = []
    lines.append('# QuickBooks Audit Transactions - Year Coverage\n')
    for zp, yrs in per_zip.items():
        total = sum(yrs.values())
        yr_list = ', '.join(str(y) for y in sorted(yrs.keys())) if yrs else 'None'
        lines.append(f'## {zp}')
        lines.append(f'- Years found: {yr_list}')
        lines.append(f'- Transaction date tokens counted: {total:,}')
        lines.append('')

    if global_years:
        min_y = min(global_years.keys())
        max_y = max(global_years.keys())
        lines.append('---')
        lines.append('## Overall')
        lines.append(f'- Span: {min_y}–{max_y}')
        lines.append(f'- Years covered: {", ".join(str(y) for y in sorted(global_years.keys()))}')
        lines.append('')

    OUT.write_text('\n'.join(lines), encoding='utf-8')
    print(f'[OK] Wrote summary: {OUT}')


if __name__ == '__main__':
    main()
