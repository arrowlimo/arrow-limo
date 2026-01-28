#!/usr/bin/env python3
"""
Normalize noisy OCR-derived CIBC missing transactions for 2012.

Input:
  - L:\\limo\\staging\\2012_comparison\\missing_cibc_transactions.csv (noisy OCR)
Output:
  - L:\\limo\\staging\\2012_comparison\\missing_cibc_transactions_normalized.csv
    Columns: transaction_date, description, debit_amount, credit_amount, source_reference

Heuristics (conservative):
- Parse date like 'Jan 3, 2012' -> YYYY-MM-DD
- Extract one monetary amount from description; if multiple found, skip unless keyword disambiguates
- Direction keywords:
  - Deposit/credit: 'CREDIT MEMO', 'MISC PAYMENT', 'E-TRANSFER', 'DEPOSIT', 'CREDIT'
  - Withdrawal/debit: 'PURCHASE', 'ABM WITHDRAWAL', 'DEBIT MEMO', 'WITHDRAWAL', 'PAYMENT' (when not preceded by 'MISC')
- Skip 'Balance forward' and 'Opening balance' lines
- Balance column is ignored (often unreliable in OCR rows)
"""
from __future__ import annotations
from pathlib import Path
import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

IN_CSV = Path(r"L:\\limo\\staging\\2012_comparison\\missing_cibc_transactions.csv")
OUT_CSV = Path(r"L:\\limo\\staging\\2012_comparison\\missing_cibc_transactions_normalized.csv")

DATE_IN_RE = re.compile(r"([A-Za-z]{3,9})\s+(\d{1,2}),\s*(\d{4})")
MONTHS = {m.lower(): i for i, m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], start=1)}
AMOUNT_RE = re.compile(r"(?<![\d,])(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})(?![\d,])")

DEPOSIT_KEYS = [
    'CREDIT MEMO','MISC PAYMENT','E-TRANSFER','DEPOSIT','CREDIT','CIBCCREDIT','CR ',  # various OCR fragments
    'E TRANSFER','E- TRANSFER','E.TRANSFER','DIRECT DEPOSIT','BANK DEPOSIT'
]
WITHDRAW_KEYS = [
    'PURCHASE','ABM WITHDRAWAL','DEBIT MEMO','WITHDRAWAL','PAYMENT','POS','ABM ',  # beware PAYMENT vs MISC PAYMENT
    'FEE','SERVICE CHARGE','NSF','TRANSFER','PREAUTHORIZED','PAD','PRE-AUTH'
]

SKIP_PHRASES = ['Balance forward','Opening balance']


def parse_date(s: str) -> str | None:
    m = DATE_IN_RE.search(s)
    if not m:
        return None
    mon = m.group(1).strip().lower()[:3]
    if mon not in MONTHS:
        return None
    try:
        return datetime(int(m.group(3)), MONTHS[mon], int(m.group(2))).strftime('%Y-%m-%d')
    except Exception:
        return None


def pick_amount(desc: str, kind: str | None):
    """Pick the most likely amount with proximity to keywords when multiple numbers exist."""
    matches = list(AMOUNT_RE.finditer(desc))
    if not matches:
        return None
    if len(matches) == 1:
        try:
            return Decimal(matches[0].group(1).replace(',', ''))
        except InvalidOperation:
            return None
    # Multiple numbers: choose the one nearest to keyword location
    up = desc.upper()
    key_positions = []
    keys = (DEPOSIT_KEYS if kind == 'credit' else WITHDRAW_KEYS) if kind else (DEPOSIT_KEYS + WITHDRAW_KEYS)
    for k in keys:
        p = up.find(k)
        if p >= 0:
            key_positions.append(p)
    if key_positions:
        center = sum(key_positions) / len(key_positions)
        matches.sort(key=lambda m: abs(m.start() - center))
        for m in matches:
            try:
                return Decimal(m.group(1).replace(',', ''))
            except InvalidOperation:
                continue
    # Fallback: last numeric token
    try:
        return Decimal(matches[-1].group(1).replace(',', ''))
    except InvalidOperation:
        return None


def classify(desc: str) -> str | None:
    up = desc.upper()
    if any(k in up for k in SKIP_PHRASES):
        return 'skip'
    # Disambiguate MISC PAYMENT as deposit side
    if 'MISC PAYMENT' in up:
        return 'credit'
    if any(k in up for k in DEPOSIT_KEYS):
        return 'credit'
    if any(k in up for k in WITHDRAW_KEYS):
        return 'debit'
    return None


def main():
    if not IN_CSV.exists():
        print(f"Input not found: {IN_CSV}")
        return
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    kept = 0
    skipped = 0
    with open(IN_CSV, 'r', encoding='utf-8', newline='') as f, open(OUT_CSV, 'w', encoding='utf-8', newline='') as out:
        r = csv.DictReader(f)
        w = csv.DictWriter(out, fieldnames=['transaction_date','description','debit_amount','credit_amount','source_reference'])
        w.writeheader()
        for row in r:
            total += 1
            date_raw = row.get('date') or ''
            desc = str(row.get('description') or '').strip()
            src = row.get('source_file') or ''
            if not desc:
                skipped += 1; continue
            if any(p in desc for p in SKIP_PHRASES):
                skipped += 1; continue
            d = parse_date(date_raw)
            if not d:
                # try also search inside description
                d = parse_date(desc)
            if not d:
                skipped += 1; continue
            kind = classify(desc)
            if kind == 'skip' or kind is None:
                skipped += 1; continue
            amt = pick_amount(desc, kind)
            if amt is None:
                skipped += 1; continue
            debit = ''
            credit = ''
            if kind == 'credit':
                credit = f"{amt:.2f}"
            elif kind == 'debit':
                debit = f"{amt:.2f}"
            w.writerow({
                'transaction_date': d,
                'description': desc,
                'debit_amount': debit,
                'credit_amount': credit,
                'source_reference': src,
            })
            kept += 1
    print(f"Normalized: kept {kept}/{total}, skipped {skipped}")


if __name__ == '__main__':
    main()
