#!/usr/bin/env python3
"""
Compare QuickBooks Monthly Summary Text Files
=============================================

Parses each extracted QuickBooks text file independently (same parsing rules as
parse_qb_reconciliation.py) and produces a side-by-side comparison report of
transaction counts and totals by classification.

Inputs:
  --files <txt1> <txt2> [...]
  --out "exports/qb/2012/qb_summaries_comparison.csv"

Output CSV columns:
  classification, count_<file1>, total_<file1>, count_<file2>, total_<file2>, diff_total (file2 - file1)

Safe: no DB writes. Read-only computations.
"""
from __future__ import annotations

import os
import re
import csv
import sys
import argparse
from datetime import datetime
from decimal import Decimal
from collections import defaultdict


WITHDRAWAL_PATTERNS = [r"\bw/d\b", r"\bwd\b", r"\bwithdrawal\b"]
FEE_PATTERNS = [r"bank\s+charges?", r"service\s+fee", r"nsf", r"non-sufficient"]
TRANSFER_PATTERNS = [r"\btsf\b", r"\btransfer\b"]


def parse_qb_line(line: str):
    # Filter non-transaction noise
    if not line.strip() or 'Beginning Balance' in line or 'Total' in line or 'Page ' in line:
        return None

    m = re.search(
        r'(Cheque|Bill Pmt|Deposit|General Journal|Cheque Expense)\s+'
        r'(\d{2}/\d{2}/\d{4})\s+'
        r'(?:(dd|WD|w/d|Auto|TSF|\d+)\s+)?'
        r'([A-Za-z0-9\s\.\'\-&]+?)\s+'
        r'(?:X\s+)?'
        r'([-]?[\d,]+\.\d{2})',
        line
    )
    if not m:
        return None

    tx_type = m.group(1)
    date_str = m.group(2)
    num = (m.group(3) or '').strip()
    vendor = m.group(4).strip()
    amount_str = m.group(5).replace(',', '')
    try:
        tx_date = datetime.strptime(date_str, '%m/%d/%Y').date()
        amount = Decimal(amount_str)
    except Exception:
        return None
    return {
        'type': tx_type,
        'date': tx_date,
        'num': num,
        'vendor': vendor,
        'amount': amount,
        'raw': line.strip(),
    }


def classify_transaction(tx: dict) -> str:
    vendor_lower = tx['vendor'].lower()
    num_lower = tx['num'].lower() if tx['num'] else ''
    # Withdrawals
    if any(re.search(p, vendor_lower, re.I) or re.search(p, num_lower, re.I) for p in WITHDRAWAL_PATTERNS):
        return 'withdrawal'
    # Fees
    if any(re.search(p, vendor_lower, re.I) for p in FEE_PATTERNS):
        return 'bank_fee'
    # Transfers
    if any(re.search(p, vendor_lower, re.I) or re.search(p, num_lower, re.I) for p in TRANSFER_PATTERNS):
        return 'transfer'
    # Journals
    if tx['type'] == 'General Journal':
        return 'journal_entry'
    # Deposits
    if tx['type'] == 'Deposit':
        return 'deposit'
    # Vendor expense (default)
    return 'vendor_expense'


def summarize_file(txt_path: str) -> dict:
    """Return dict: classification -> {'count': n, 'total': Decimal}"""
    by_class = defaultdict(lambda: {'count': 0, 'total': Decimal('0')})
    with open(txt_path, 'r', encoding='utf-8') as f:
        for line in f:
            tx = parse_qb_line(line)
            if not tx:
                continue
            cls = classify_transaction(tx)
            by_class[cls]['count'] += 1
            by_class[cls]['total'] += tx['amount']
    return by_class


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--files', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    if len(args.files) < 2:
        print('Provide at least two extracted text files to compare.')
        return 1

    # Summarize each file
    file_summaries = []
    for path in args.files:
        if not os.path.exists(path):
            print(f'[FAIL] Not found: {path}')
            return 1
        print(f'⏳ Summarizing {path} ...')
        file_summaries.append((os.path.basename(path), summarize_file(path)))

    # Union of classifications
    classes = set()
    for _, summary in file_summaries:
        classes.update(summary.keys())
    classes = sorted(classes)

    # Prepare CSV output
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        header = ['classification']
        for name, _ in file_summaries:
            base = os.path.splitext(name)[0]
            header.extend([f'count_{base}', f'total_{base}'])
        # If exactly two files, include diff column
        if len(file_summaries) == 2:
            header.append('diff_total_(file2_minus_file1)')
        w.writerow(header)

        for cls in classes:
            row = [cls]
            totals = []
            for _, summary in file_summaries:
                cnt = summary.get(cls, {}).get('count', 0)
                tot = summary.get(cls, {}).get('total', Decimal('0'))
                row.extend([cnt, f"{tot:.2f}"])
                totals.append(tot)
            if len(totals) == 2:
                diff = totals[1] - totals[0]
                row.append(f"{diff:.2f}")
            w.writerow(row)

    print(f'[OK] Wrote comparison: {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
