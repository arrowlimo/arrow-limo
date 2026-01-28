#!/usr/bin/env python3
"""
Rebuild compiled CIBC all.csv files per account from yearly CSVs.
- Merges 2018..current year files in account folder
- Normalizes dates, sorts ascending, deduplicates exact duplicates
- Writes <account> all.csv with original column order preserved

Usage:
  python scripts/rebuild_cibc_all.py --account 8362
  python scripts/rebuild_cibc_all.py --account 8117
  python scripts/rebuild_cibc_all.py --account 4462
  python scripts/rebuild_cibc_all.py --all

Notes:
- Read-only on yearly CSVs; only overwrites the all.csv output file.
- Handles YYYY-MM-DD and M/D/YYYY date formats.
"""
import argparse
import csv
import glob
import os
from datetime import datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CIBC = os.path.join(ROOT, 'CIBC UPLOADS')

ACCOUNT_DIRS = {
    '8362': '0228362 (CIBC checking account)',
    '8117': '3648117 (CIBC Business Deposit account, alias for 0534',
    '4462': '8314462 (CIBC vehicle loans)',
}

YEAR_PATTERN = {
    '8362': 'cibc 8362 *.csv',
    '8117': 'cibc 8117 *.csv',
    '4462': 'cibc 4462 *.csv',
}

ALL_FILENAME = {
    '8362': 'cibc 8362 all.csv',
    '8117': 'cibc 8117 all.csv',
    '4462': 'cibc 4462 all.csv',
}


def parse_date(text: str):
    text = text.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%-m/%-d/%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    raise ValueError(f'Unrecognized date: {text}')


def rebuild(account_code: str) -> str:
    acct_dir = os.path.join(CIBC, ACCOUNT_DIRS[account_code])
    pattern = os.path.join(acct_dir, YEAR_PATTERN[account_code])
    files = sorted(glob.glob(pattern))
    files = [f for f in files if ' all.csv' not in f.lower()]
    if not files:
        return f"No yearly CSVs found for {account_code} in {acct_dir}"

    rows = []
    header = None
    for path in files:
        with open(path, newline='', encoding='utf-8-sig') as f:
            r = csv.reader(f)
            for i, row in enumerate(r):
                if not row:
                    continue
                # Some year files have no header; treat all as data lines
                if header is None and (i == 0 and '-' in row[0] and row[0].count('-') == 2):
                    # Looks like YYYY-MM-DD; assume no header
                    pass
                # Keep original row structure
                rows.append(row)
    # Normalize date and build sort key
    enriched = []
    for row in rows:
        try:
            d = parse_date(row[0])
        except Exception:
            # skip lines without a valid date
            continue
        enriched.append((d, tuple(row)))
    # Deduplicate exact duplicates
    seen = set()
    unique = []
    for d, tup in enriched:
        if tup in seen:
            continue
        seen.add(tup)
        unique.append((d, tup))
    unique.sort(key=lambda x: x[0])

    out_path = os.path.join(acct_dir, ALL_FILENAME[account_code])
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        for d, tup in unique:
            w.writerow(list(tup))
    return f"Rebuilt {out_path} with {len(unique)} rows from {len(files)} files"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--account', choices=['8362','8117','4462'])
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    targets = ['8362','8117','4462'] if args.all else [args.account]
    for code in targets:
        if code is None:
            continue
        print(rebuild(code))

if __name__ == '__main__':
    main()
