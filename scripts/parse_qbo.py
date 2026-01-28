#!/usr/bin/env python3
"""
Parse .qbo/.ofx files and export transactions to CSV.
Usage:
    Single file: python scripts/parse_qbo.py --file "L:\\limo\\CIBC UPLOADS\\verify this data\\New folder\\pcbanking (1).qbo"
    Bulk folder: python scripts/parse_qbo.py --dir  "L:\\limo\\CIBC UPLOADS\\verify this data"
Outputs CSV at reports/qbo_transactions.csv and errors at reports/qbo_errors.csv (for bulk).
"""
import os
import csv
import argparse
from datetime import datetime

# Compatibility shim for ofxparse on Python 3.10+
import collections
try:
    from collections.abc import Iterable, Mapping
    if not hasattr(collections, 'Iterable'):
        collections.Iterable = Iterable  # type: ignore[attr-defined]
    if not hasattr(collections, 'Mapping'):
        collections.Mapping = Mapping  # type: ignore[attr-defined]
except Exception:
    pass

from ofxparse import OfxParser

REPORTS_DIR = r"L:\\limo\\reports"
os.makedirs(REPORTS_DIR, exist_ok=True)

OUT_CSV = os.path.join(REPORTS_DIR, 'qbo_transactions.csv')
ERR_CSV = os.path.join(REPORTS_DIR, 'qbo_errors.csv')


def parse_qbo(file_path: str):
    with open(file_path, 'rb') as f:
        ofx = OfxParser.parse(f)
    rows = []
    for acct in ofx.accounts:
        bankid = getattr(acct, 'bankid', '')
        acctid = getattr(acct, 'account_id', '') or getattr(acct, 'number', '')
        accttype = getattr(acct, 'account_type', '')
        for tx in acct.statement.transactions:
            rows.append({
                'bankid': bankid,
                'account_id': acctid,
                'account_type': accttype,
                'date': tx.date.strftime('%Y-%m-%d') if isinstance(tx.date, datetime) else str(tx.date),
                'amount': f"{tx.amount:.2f}",
                'fitid': tx.id,
                'payee': tx.payee,
                'memo': tx.memo,
                'checknum': tx.checknum,
                'type': tx.type,
            })
    return rows


def main():
    p = argparse.ArgumentParser(description='Parse .qbo/.ofx to CSV')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--file', help='Path to .qbo/.ofx file')
    g.add_argument('--dir',  help='Folder to scan recursively for .qbo/.ofx')
    args = p.parse_args()

    fieldnames = ['source_file','bankid','account_id','account_type','date','amount','fitid','payee','memo','checknum','type']

    if args.file:
        file_path = args.file
        if not os.path.isfile(file_path):
            print(f"File not found: {file_path}")
            return 1
        try:
            rows = parse_qbo(file_path)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return 1
        for r in rows:
            r['source_file'] = file_path
        with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"Parsed {len(rows)} transactions from {file_path}\nSaved: {OUT_CSV}")
        return 0

    # Bulk folder mode
    total = 0
    errors = []
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as outf:
        w = csv.DictWriter(outf, fieldnames=fieldnames)
        w.writeheader()
        for root, dirs, files in os.walk(args.dir):
            for name in files:
                ext = os.path.splitext(name)[1].lower()
                if ext not in ('.qbo', '.ofx'):
                    continue
                path = os.path.join(root, name)
                try:
                    rows = parse_qbo(path)
                    for r in rows:
                        r['source_file'] = path
                    w.writerows(rows)
                    total += len(rows)
                except Exception as e:
                    errors.append({'file': path, 'error': str(e)})
    if errors:
        with open(ERR_CSV, 'w', newline='', encoding='utf-8') as ef:
            ew = csv.DictWriter(ef, fieldnames=['file','error'])
            ew.writeheader()
            ew.writerows(errors)
    print(f"Parsed {total} transactions from {args.dir} (qbo/ofx)\nSaved: {OUT_CSV}\nErrors: {len(errors)} -> {ERR_CSV if errors else 'none'}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
