#!/usr/bin/env python3
import sys
import os
import re
import csv
from collections import Counter

KEYWORDS = [
    b'QuickBooks', b'QBB', b'QBM', b'QBW', b'IIF',
    b'ARROW', b'Arrow', b'Limo', b'Limousine', b'Invoice', b'INVOICE',
    b'Customer', b'CUSTOMER', b'Vendor', b'VENDOR', b'Employee', b'EMPLOYEE',
    b'2007', b'2008', b'2009', b'2010', b'2011',
]

PRINTABLE_RE = re.compile(rb'[\x20-\x7E]{6,}')
DATE_YMD = re.compile(rb'\b(20\d{2})[-/\.](0[1-9]|1[0-2])[-/\.](0[1-9]|[12]\d|3[01])\b')
DATE_MDY = re.compile(rb'\b(0?[1-9]|1[0-2])[-/\.](0?[1-9]|[12]\d|3[01])[-/\.]((19|20)\d{2})\b')
MONTH_NAMES = re.compile(rb'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},\s+(19|20)\d{2}\b', re.IGNORECASE)

MAGIC_SIGS = {
    b'PK\x03\x04': 'ZIP-like',
    b'MSCF': 'CAB',
    b'QBM': 'QuickBooks Portable Company File',
    b'QBB': 'QuickBooks Backup',
}


def main():
    if len(sys.argv) < 2:
        print('Usage: scan_qbb.py <path-to-qbb> [output-csv]')
        sys.exit(2)
    path = sys.argv[1]
    out_csv = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(path), 'qbb_strings_sample.csv')

    with open(path, 'rb') as f:
        data = f.read()

    # Magic signatures
    magic = None
    for sig, name in MAGIC_SIGS.items():
        if data.startswith(sig):
            magic = name
            break
    print(f'Magic signature: {magic or "(unknown)"}')

    # Printable strings
    strings = PRINTABLE_RE.findall(data)
    print(f'Printable ASCII strings found: {len(strings)}')

    # Keyword hits
    hits_summary = []
    for kw in KEYWORDS:
        hits = [s for s in strings if kw in s]
        if hits:
            sample = [h.decode('latin1','ignore') for h in hits[:10]]
            hits_summary.append((kw.decode(), len(hits), sample))
    for kw, count, sample in hits_summary:
        print(f'== {kw} ({count}) ==')
        for s in sample:
            print('  ', s)

    # Dates
    dates = set()
    for m in DATE_YMD.finditer(data):
        dates.add(m.group(0))
    for m in DATE_MDY.finditer(data):
        dates.add(m.group(0))
    for m in MONTH_NAMES.finditer(data):
        dates.add(m.group(0))
    dates_dec = sorted([d.decode('latin1','ignore') for d in dates])
    print(f'Date-like tokens found: {len(dates_dec)}')
    for s in dates_dec[:20]:
        print('  ', s)

    # Export a small sample of strings for manual inspection
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['string'])
        for s in strings[:2000]:
            w.writerow([s.decode('latin1','ignore')])
    print('Sample strings CSV:', out_csv)


if __name__ == '__main__':
    main()
