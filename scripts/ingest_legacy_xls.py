import os, sys, json, re
from pathlib import Path
import pandas as pd

# Minimal categorization by filename
CATS = [
    (r'payroll|pay\s*stub|ytd|hourly|pd7a|pdta|vacation', 'Payroll'),
    (r't4|efile|cra|gst|hst|reconcile', 'CRA/Taxes'),
    (r'cibc|scotia|bank|statement|pcbanking', 'Banking'),
    (r'accounts?\s*payable|ap\b', 'Accounts Payable'),
    (r'lease|leasing|heffner', 'Leasing'),
    (r'invoice|receipt', 'Invoices/Receipts'),
]


def categorize(name: str) -> str:
    n = name.lower()
    for pat, cat in CATS:
        if re.search(pat, n):
            return cat
    return 'Uncategorized'


def main():
    if len(sys.argv) < 2:
        print('Usage: python ingest_legacy_xls.py <folder> [--year 2012]')
        sys.exit(1)
    folder = Path(sys.argv[1])
    year = None
    if len(sys.argv) >= 4 and sys.argv[2] == '--year':
        year = sys.argv[3]

    out_dir = Path('exports/docs/legacy_xls_csv')
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for entry in os.scandir(folder):
        if not entry.is_file():
            continue
        p = Path(entry.path)
        if p.suffix.lower() != '.xls':
            continue
        try:
            xls = pd.ExcelFile(str(p), engine='xlrd')
            for sheet in xls.sheet_names:
                try:
                    df = xls.parse(sheet, header=0)
                    # Drop fully empty columns
                    df = df.dropna(how='all', axis=1)
                    # Optional: year filter if a date column exists
                    if year:
                        for col in df.columns:
                            if df[col].dtype.kind in 'M':
                                s = pd.to_datetime(df[col], errors='coerce')
                                mask = s.dt.year.astype('Int64') == int(year)
                                if mask.notna().any():
                                    df = df[mask.fillna(False)]
                                    break
                    out_name = f"{p.stem}_{re.sub(r'[^A-Za-z0-9]+','_',sheet)}.csv"
                    out_path = out_dir / out_name
                    df.to_csv(out_path, index=False)
                    results.append({
                        'file': p.name,
                        'sheet': sheet,
                        'rows': int(len(df)),
                        'cols': [str(c) for c in df.columns[:32]],
                        'category': categorize(p.name),
                        'out': str(out_path)
                    })
                except Exception as e:
                    results.append({'file': p.name, 'sheet': sheet, 'error': str(e)})
        except Exception as e:
            results.append({'file': p.name, 'error': str(e)})

    # Write a summary file
    with (out_dir / 'summary.json').open('w', encoding='utf-8') as f:
        json.dump({'parsed': results}, f, indent=2)

    # Also produce a quick Markdown summary
    lines = ['# Legacy .xls ingestion summary', '']
    ok = [r for r in results if 'rows' in r]
    errs = [r for r in results if 'error' in r]
    lines.append(f"Parsed sheets: {len(ok)}; Errors: {len(errs)}")
    lines.append('')
    # Top files
    by_file = {}
    for r in ok:
        by_file.setdefault(r['file'], []).append(r)
    for fname, sheets in sorted(by_file.items()):
        total_rows = sum(r['rows'] for r in sheets)
        cat = sheets[0]['category'] if sheets else 'Uncategorized'
        lines.append(f"## {fname} [{cat}] (rows: {total_rows})")
        for r in sheets:
            lines.append(f"- {r['sheet']}: {r['rows']} rows; cols: {', '.join(r['cols'])}")
        lines.append('')
    with (out_dir / 'summary.md').open('w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(json.dumps({'ok': len(ok), 'errors': len(errs), 'out_dir': str(out_dir)}, indent=2))

if __name__ == '__main__':
    main()
