#!/usr/bin/env python3
"""
Parse Scotiabank 2012 statement PDFs to line-level transactions (OCR tolerant) and emit normalized CSV.

Inputs (PDFs):
  - L:\\limo\\pdf\\2012 scotia bank statements_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 2_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 3_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 4_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 5_ocred.pdf
  - L:\\limo\\pdf\\2012 scotia bank statements 6_ocred.pdf

Outputs:
  - L:\\limo\\staging\\2012_comparison\\scotia_statement_transactions_2012_raw.csv
  - L:\\limo\\staging\\2012_comparison\\scotia_statement_transactions_2012_normalized.csv

Safe: Read-only to PDFs; produces CSVs for staging (no DB writes here).
"""
from __future__ import annotations
from pathlib import Path
import re
import csv
from decimal import Decimal, InvalidOperation
import pdfplumber
from datetime import datetime
from collections import defaultdict
from statistics import mean

INPUT_FILES = [
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 2_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 3_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 4_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 5_ocred.pdf"),
    Path(r"L:\\limo\\pdf\\2012 scotia bank statements 6_ocred.pdf"),
]
ROOT = Path(r"L:\\limo\\staging\\2012_comparison")
OUT_RAW = ROOT / 'scotia_statement_transactions_2012_raw.csv'
OUT_NORM = ROOT / 'scotia_statement_transactions_2012_normalized.csv'

# Date patterns: textual and numeric
DATE_TXT = re.compile(r"([A-Za-z]{3,9})\s+(\d{1,2}),\s*(20)?(\d{2})")
MONTHS = {m.lower(): i for i, m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], start=1)}
DATE_NUM = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](?:20)?(\d{2})")

AMOUNT_RE = re.compile(r"\(?-?\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})\)?")

DEPOSIT_KEYS = ['DEPOSIT','CREDIT','E-TRANSFER','E TRANSFER','DIRECT DEPOSIT']
WITHDRAW_KEYS = [
    'WITHDRAWAL', 'WITHDRAW', 'PAYMENT', 'CHEQUE', 'ABM', 'PURCHASE', 'POS', 'FEE',
    'SERVICE CHARGE', 'NSF', 'PAD', 'DEBIT', 'DEBIT MEMO', 'INSURANCE', 'RENT/LEASE', 'RENT', 'LEASE'
]
SKIP_KEYS = ['BALANCE FORWARD','OPENING BALANCE','CLOSING BALANCE','PAGE','ACCOUNT','BUSINESS ACCOUNT']

# Noise and card-last4 handling
CHECKMARKS = {'✓','✔','■','▮','▯','•','·'}
LINE_CHARS = set('-=–-_~|•·*+')
DEFAULT_LAST4 = '7501'  # user-provided last four
CARD_LAST4_RE = re.compile(r"(visa|mastercard|amex|card|credit|debit)[^\d]{0,8}(?:\*+|x+|X+)?\s*(\d{4})", re.IGNORECASE)

def is_noise_line(ln: str) -> bool:
    s = ln.strip()
    if not s:
        return True
    # Check for lines dominated by line-drawing/symbol characters
    if s and sum(c in LINE_CHARS for c in s) / max(len(s), 1) > 0.7:
        return True
    # Lines that are mostly non-alnum
    alnum = sum(ch.isalnum() for ch in s)
    if alnum / max(len(s), 1) < 0.2:
        # Allow if contains a clear money amount
        if not AMOUNT_RE.search(s):
            return True
    # Lines that are just checkmark-like glyphs
    if set(s) <= CHECKMARKS:
        return True
    return False


def parse_date_any(s: str) -> str | None:
    s = s.strip()
    m = DATE_TXT.search(s)
    if m:
        mon = MONTHS.get(m.group(1).lower()[:3])
        if mon:
            dd = int(m.group(2))
            yy = int(m.group(4)) + 2000
            try:
                return datetime(yy, mon, dd).strftime('%Y-%m-%d')
            except Exception:
                pass
    m2 = DATE_NUM.search(s)
    if m2:
        mm, dd, yy = int(m2.group(1)), int(m2.group(2)), int(m2.group(3)) + 2000
        try:
            return datetime(yy, mm, dd).strftime('%Y-%m-%d')
        except Exception:
            pass
    return None


def extract_lines(path: Path) -> list[dict]:
    out = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            text = p.extract_text() or ''
            for ln in text.splitlines():
                if not ln.strip():
                    continue
                up = ln.upper()
                if any(k in up for k in SKIP_KEYS):
                    continue
                if is_noise_line(ln):
                    continue
                date = parse_date_any(ln)
                # If no date at start, try first token
                if not date:
                    tokens = ln.split()
                    if tokens:
                        date = parse_date_any(tokens[0])
                # Skip pure card-last4 info lines (e.g., 'VISA **** 7501') unless they also have a transaction amount and keyword
                m4 = CARD_LAST4_RE.search(ln)
                if m4 and m4.group(2) == DEFAULT_LAST4:
                    if not any(k in up for k in (DEPOSIT_KEYS + WITHDRAW_KEYS)) and not AMOUNT_RE.search(ln):
                        continue
                # Pull all numbers; assume last is amount column
                nums = list(AMOUNT_RE.finditer(ln))
                amount = None
                if nums:
                    tok = nums[-1].group(1)
                    try:
                        amount = Decimal(tok.replace(',', ''))
                    except InvalidOperation:
                        amount = None
                out.append({'source': str(path), 'line': ln, 'date': date, 'amount': str(amount) if amount is not None else ''})
    return out


def write_raw(rows: list[dict]):
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_RAW, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['source','line','date','amount'])
        w.writeheader(); w.writerows(rows)


def normalize_rows(rows: list[dict]) -> list[dict]:
    norm = []
    for r in rows:
        date = r.get('date')
        ln = r.get('line','')
        if not date:
            continue
        up = ln.upper()
        if any(k in up for k in SKIP_KEYS):
            continue
        # Direction based on keywords
        kind = None
        if any(k in up for k in DEPOSIT_KEYS):
            kind = 'credit'
        elif any(k in up for k in WITHDRAW_KEYS):
            kind = 'debit'
        # Find amount
        nums = list(AMOUNT_RE.finditer(ln))
        if not nums:
            continue
        # Choose the most plausible transaction amount on the line:
        # - Prefer the smallest absolute value (to avoid picking the larger running balance)
        candidates = []
        for m in nums:
            tok = m.group(1)
            try:
                val = Decimal(tok.replace(',', ''))
            except InvalidOperation:
                continue
            candidates.append(val)
        if not candidates:
            continue
        # Select by smallest absolute magnitude
        amt = min(candidates, key=lambda v: abs(v))
        # Safety: discard implausibly large values (likely balances)
        if abs(amt) > Decimal('60000'):
            continue
        debit = ''
        credit = ''
        if kind == 'credit':
            credit = f"{amt:.2f}"
        elif kind == 'debit':
            debit = f"{amt:.2f}"
        else:
            # Unknown; keep as credit if positive mention of deposit/credit occurs, else skip
            continue
        norm.append({
            'transaction_date': date,
            'description': ln.strip(),
            'debit_amount': debit,
            'credit_amount': credit,
            'source_reference': r.get('source','')
        })
    return norm


def write_normalized(rows: list[dict]):
    with open(OUT_NORM, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['transaction_date','description','debit_amount','credit_amount','source_reference'])
        w.writeheader(); w.writerows(rows)


def _kmeans1d(values: list[float], k: int) -> tuple[list[float], list[int]]:
    """Simple 1D k-means clustering.
    Returns (centroids, labels) with labels aligned to input values order.
    If unique values < k, reduces k accordingly.
    """
    if not values:
        return [], []
    uniq = sorted(set(values))
    k = min(k, len(uniq))
    # Initialize centroids using min/median/max heuristic
    if k == 1:
        cents = [mean(values)]
    elif k == 2:
        cents = [min(values), max(values)]
    else:
        cents = [min(values), uniq[len(uniq)//2], max(values)]
    labels = [0] * len(values)
    for _ in range(8):  # few iterations suffice for 1D
        # Assign
        for i, v in enumerate(values):
            labels[i] = min(range(len(cents)), key=lambda j: abs(v - cents[j]))
        # Recompute
        new_cents = []
        for j in range(len(cents)):
            cluster_vals = [v for v, lab in zip(values, labels) if lab == j]
            if cluster_vals:
                new_cents.append(mean(cluster_vals))
            else:
                new_cents.append(cents[j])
        # Converged?
        if all(abs(a - b) < 0.5 for a, b in zip(cents, new_cents)):
            cents = new_cents
            break
        cents = new_cents
    return cents, labels


def normalize_rows_columnar(pdf_path: Path) -> list[dict]:
    """Column-aware normalization using x-position clustering per page.
    Detect right-aligned numeric columns (withdrawal, deposit, balance) by clustering x1 positions.
    """
    rows_out: list[dict] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages:
                words = p.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False, use_text_flow=False) or []
                # Collect numeric tokens with geometry
                nums = []  # each: {x0,x1,top,bottom,text,val}
                for w in words:
                    txt = w.get('text', '')
                    m = AMOUNT_RE.fullmatch(txt.strip()) or AMOUNT_RE.search(txt)
                    if not m:
                        continue
                    tok = m.group(1)
                    try:
                        val = Decimal(tok.replace(',', ''))
                    except InvalidOperation:
                        continue
                    nums.append({
                        'x0': float(w['x0']), 'x1': float(w['x1']),
                        'top': float(w['top']), 'bottom': float(w['bottom']),
                        'text': txt, 'val': val
                    })

                if not nums:
                    continue
                # Cluster x1 into up to 3 columns
                x1s = [n['x1'] for n in nums]
                cents, labels = _kmeans1d(x1s, 3)
                # Map clusters to logical columns by x1 (ascending = left→right)
                order = sorted(range(len(cents)), key=lambda j: cents[j])
                col_map = {order[0]: 'withdrawal'}
                if len(cents) >= 2:
                    col_map[order[1]] = 'deposit'
                if len(cents) >= 3:
                    col_map[order[2]] = 'balance'

                # Assign labels back to nums
                for n, lab in zip(nums, labels):
                    n['col'] = col_map.get(lab, 'unknown')

                # Group by row using y proximity
                rows_by_y: dict[int, list[dict]] = defaultdict(list)
                for n in nums:
                    key = int(round(n['top']))
                    rows_by_y[key].append(n)

                # Build line text per y by joining source text words on same y band
                text_by_y: dict[int, str] = {}
                words_by_y: dict[int, list[str]] = defaultdict(list)
                for w in words:
                    key = int(round(float(w['top'])))
                    words_by_y[key].append(w.get('text', ''))
                for key, wlist in words_by_y.items():
                    text_by_y[key] = ' '.join(wlist)

                for key, items in rows_by_y.items():
                    # Determine amounts per column
                    debit_amt = None
                    credit_amt = None
                    bal_amt = None
                    # Pick the amount closest to centroid within each column
                    by_col = defaultdict(list)
                    for it in items:
                        by_col[it['col']].append(it)
                    if by_col.get('withdrawal'):
                        # choose numerically smallest abs to avoid any merged noise
                        debit_amt = min((x['val'] for x in by_col['withdrawal']), key=lambda v: abs(v))
                    if by_col.get('deposit'):
                        credit_amt = min((x['val'] for x in by_col['deposit']), key=lambda v: abs(v))
                    if by_col.get('balance'):
                        bal_amt = min((x['val'] for x in by_col['balance']), key=lambda v: abs(v))

                    # Safety filters against balance mis-pick
                    if debit_amt is not None and abs(debit_amt) > Decimal('60000'):
                        debit_amt = None
                    if credit_amt is not None and abs(credit_amt) > Decimal('60000'):
                        credit_amt = None

                    if debit_amt is None and credit_amt is None:
                        continue  # not a transaction row

                    # Extract date presence on this line
                    desc = text_by_y.get(key, '')
                    date = parse_date_any(desc)
                    # If no inline date, try to infer by scanning near y neighbors (+/-2)
                    if not date:
                        for dkey in (key-1, key+1, key-2, key+2):
                            if dkey in text_by_y:
                                maybe = parse_date_any(text_by_y[dkey])
                                if maybe:
                                    date = maybe; break

                    if not date:
                        # If we can't find a date on/near the row, skip; too risky
                        continue
                    # Only keep 2012 transactions (expected focus)
                    if not date.startswith('2012-'):
                        continue

                    # Heuristic correction: align sign with keywords if columns appear swapped on this page
                    up = desc.upper()
                    has_deposit_kw = any(k in up for k in DEPOSIT_KEYS)
                    has_withdraw_kw = any(k in up for k in WITHDRAW_KEYS)
                    # If line looks like a withdrawal but landed in credit column, swap
                    if has_withdraw_kw and credit_amt is not None and debit_amt is None:
                        debit_amt, credit_amt = credit_amt, None
                    # If line looks like a deposit but landed in debit column, swap
                    if has_deposit_kw and debit_amt is not None and credit_amt is None:
                        credit_amt, debit_amt = debit_amt, None

                    rows_out.append({
                        'transaction_date': date,
                        'description': desc.strip(),
                        'debit_amount': f"{debit_amt:.2f}" if debit_amt is not None else '',
                        'credit_amount': f"{credit_amt:.2f}" if credit_amt is not None else '',
                        'source_reference': str(pdf_path)
                    })
    except Exception as e:
        print(f"WARN: Columnar parsing failed for {pdf_path}: {e}")
    return rows_out


def main():
    all_rows = []
    norm_rows = []
    for p in INPUT_FILES:
        if p.exists():
            try:
                # Keep raw text capture for audit
                all_rows.extend(extract_lines(p))
            except Exception as e:
                print(f"WARN: Failed to parse {p}: {e}")
            # Column-aware normalized rows per PDF
            norm_rows.extend(normalize_rows_columnar(p))
    # Write raw OCR lines (diagnostic)
    write_raw(all_rows)
    # Fallback: if column-aware extracted nothing, use keyword/heuristic normalization on raw lines
    final_norm = norm_rows if norm_rows else normalize_rows(all_rows)
    write_normalized(final_norm)
    print(f"Parsed lines: {len(all_rows)} | Normalized transactions: {len(final_norm)} (column-aware: {len(norm_rows)})")
    print(f"Raw: {OUT_RAW}\nNormalized: {OUT_NORM}")


if __name__ == '__main__':
    main()
