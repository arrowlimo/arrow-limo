#!/usr/bin/env python3
"""
Scotia Bank Statement Reconciliation Parser & Validator

Purpose:
  Parse a Scotia bank statement printout (text or PDF) for account 3714081 (configurable),
  validate running balances, and cross-check each transaction against banking_transactions.

Features:
  - Accepts .txt or .pdf input via --input
  - Auto-detects page headers and skips non-transaction lines
  - Date pattern support: DD-MMM-YYYY, DD-MMM, MMM DD, YYYY-MM-DD
  - Extracts: date, description, debit, credit, balance
  - Running balance verification (previous_balance +/- amount == current_balance)
  - DB reconciliation: match by (date, amount side, description exact or fuzzy)
  - Duplicate detection: multiple statement lines mapping to one DB row
  - Missing detection: statement transaction absent in DB
  - JSON summary output (--output-json path)
  - Dry-run only; no DB modifications performed.

Usage:
  python reconcile_scotia_statement.py --input path/to/statement.pdf --year 2012 --account 3714081 --output-json scotia_2012.json

Assumptions:
  - banking_transactions table contains rows with account_number matching the Scotia account
  - debit_amount represents money leaving; credit_amount represents money coming in

Limitations:
  - Requires decent OCR extraction for PDFs; for poor scans convert to text first externally
  - Running balance logic: first balance becomes starting point; subsequent lines validated sequentially

"""

import os
import re
import sys
import json
import argparse
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

try:
    import psycopg2
except ImportError:
    psycopg2 = None

# Optional PDF extraction
PDF_AVAILABLE = False
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

DATE_PATTERNS = [
    # Order matters; more specific first
    (re.compile(r'^(\d{1,2})-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{4})$'), '%d-%b-%Y'),
    (re.compile(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})$'), '%b %d'),
    (re.compile(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$'), '%d %b'),
    (re.compile(r'^(\d{4})-(\d{2})-(\d{2})$'), '%Y-%m-%d'),
    (re.compile(r'^(\d{2})/(\d{2})/(\d{4})$'), '%m/%d/%Y'),  # added mm/dd/YYYY for OCR lines
]

MONTH_MAP = {
    'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,
    'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12
}

AMOUNT_RE = re.compile(r'[-+]?[0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})')

# Headers that start new transactional segments (baseline resets)
SEGMENT_START_PATTERNS = [
    re.compile(r'^Cheques and Payments'),
    re.compile(r'^Deposits and Credits'),
    re.compile(r'^New Transactions'),
]

# Lines to skip entirely (totals / non-transaction summaries)
SKIP_NON_TRANSACTION_PATTERNS = [
    re.compile(r'^Beginning Balance'),
    re.compile(r'^Cleared Transactions'),
    re.compile(r'^Total Cheques and Payments'),
    re.compile(r'^Total Deposits and Credits'),
    re.compile(r'^Total Cleared Transactions'),
    re.compile(r'^Cleared Balance'),
    re.compile(r'^Register Balance'),
    re.compile(r'^Ending Balance'),
    re.compile(r'^Total New Transactions'),
]

def parse_args():
    ap = argparse.ArgumentParser(description="Scotia bank statement reconciliation")
    ap.add_argument('--input', required=True, help='Input PDF or text statement file')
    ap.add_argument('--year', type=int, default=None, help='Target year (used to fill missing years in partial dates)')
    ap.add_argument('--account', default='3714081', help='Scotia bank account number in banking_transactions')
    ap.add_argument('--output-json', help='Write JSON summary to path')
    ap.add_argument('--limit', type=int, default=None, help='Limit number of parsed transactions for testing')
    ap.add_argument('--verbose', action='store_true', help='Verbose line parsing output')
    ap.add_argument('--enforce-year', action='store_true', help='Drop parsed entries whose date year differs from --year')
    return ap.parse_args()

def load_lines(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.pdf':
        if not PDF_AVAILABLE:
            raise RuntimeError('pdfplumber not installed; cannot parse PDF')
        lines = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                for raw_line in text.splitlines():
                    line = raw_line.rstrip('\n')
                    if line.strip():
                        lines.append(line)
        return lines
    else:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return [l.rstrip('\n') for l in f if l.strip()]

MULTIDATE_PATTERN = re.compile(r'(\d{2}/\d{2}/\d{4})')

def explode_multidate_lines(lines):
    """Split lines that contain more than one explicit mm/dd/YYYY date into separate lines.
    Keeps the date token at the start of each resulting slice.
    """
    exploded = []
    for line in lines:
        matches = list(MULTIDATE_PATTERN.finditer(line))
        if len(matches) <= 1:
            exploded.append(line)
            continue
        # Build slices
        for i, m in enumerate(matches):
            start = m.start()
            end = matches[i+1].start() if i+1 < len(matches) else len(line)
            slice_text = line[start:end].strip()
            exploded.append(slice_text)
    return exploded

def normalize_whitespace(s):
    return re.sub(r'\s+', ' ', s).strip()

def try_parse_date(token, year_hint=None):
    token = token.strip()
    for regex, fmt in DATE_PATTERNS:
        m = regex.match(token)
        if m:
            if fmt == '%b %d':
                if year_hint is None:
                    return None
                month = MONTH_MAP[m.group(1)]
                day = int(m.group(2))
                return date(year_hint, month, day)
            if fmt == '%d %b':
                if year_hint is None:
                    return None
                day = int(m.group(1))
                month = MONTH_MAP[m.group(2)]
                return date(year_hint, month, day)
            if fmt == '%d-%b-%Y':
                return datetime.strptime(token, '%d-%b-%Y').date()
            if fmt == '%Y-%m-%d':
                return datetime.strptime(token, '%Y-%m-%d').date()
            if fmt == '%m/%d/%Y':
                return datetime.strptime(token, '%m/%d/%Y').date()
    return None

def extract_amount(field):
    field = field.replace('$','').strip()
    # find first numeric pattern
    m = AMOUNT_RE.search(field)
    if not m:
        return None
    raw = m.group(0).replace(',','')
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None

def classify_line(line, year_hint=None):
    """Parse a single OCR line.
    Enhanced to locate a date token anywhere (not just first) and account for lines that start with 'Cheque', 'General', etc.
    Strategy:
      1. Split into tokens; find first token matching a date.
      2. Identify all amount tokens; require at least 2 (amount + balance).
      3. Description is everything except date token and the final two amount tokens.
    """
    parts = normalize_whitespace(line).split(' ')
    if not parts:
        return None
    date_idx = None
    tx_date = None
    for i, tok in enumerate(parts):
        tx_date = try_parse_date(tok, year_hint)
        if tx_date:
            date_idx = i
            break
    if not tx_date:
        return None
    # Collect amount tokens (strict fullmatch)
    amount_tokens = [p for p in parts if AMOUNT_RE.fullmatch(p.replace('$',''))]
    if len(amount_tokens) < 2:
        return None
    balance_token = amount_tokens[-1]
    amount_token = amount_tokens[-2]
    amount = extract_amount(amount_token)
    balance = extract_amount(balance_token)
    # Build description excluding chosen tokens
    exclusion = set([parts[date_idx], amount_token, balance_token])
    description_tokens = [p for i,p in enumerate(parts) if p not in exclusion]
    description = ' '.join(description_tokens).strip()
    return {
        'date': tx_date.isoformat(),
        'description': description,
        'raw_amount': float(amount) if amount is not None else None,
        'balance': float(balance) if balance is not None else None,
        'source_line': line
    }

def running_balance_check(entries):
    """Validate running balances per segment.
    Each segment resets baseline at its first transaction.
    Direction inference: choose +/- that matches observed change; if neither matches within 0.01 tolerance, record problem.
    """
    problems = []
    # Group by segment
    segments = {}
    for idx, e in enumerate(entries):
        seg_id = e.get('segment_id', 0)
        segments.setdefault(seg_id, []).append((idx, e))
    for seg_id, rows in sorted(segments.items()):
        if not rows:
            continue
        # baseline: first row's balance – accept as-is
        prev_balance = rows[0][1].get('balance')
        for local_i in range(1, len(rows)):
            global_index, cur = rows[local_i]
            amt = cur.get('raw_amount')
            bal = cur.get('balance')
            if amt is None or bal is None or prev_balance is None:
                prev_balance = bal
                continue
            expected_add = round(prev_balance + amt, 2)
            expected_sub = round(prev_balance - amt, 2)
            actual = round(bal, 2)
            if actual == expected_add or actual == expected_sub:
                # Determine direction and store for later inspection
                if actual == expected_sub:
                    cur['inferred_direction'] = 'debit'  # balance decreased by amount
                elif actual == expected_add:
                    cur['inferred_direction'] = 'credit'
                prev_balance = bal
                continue
            problems.append({
                'segment_id': seg_id,
                'index': global_index,
                'prev_balance': prev_balance,
                'amount': amt,
                'balance': bal,
                'expected_add': expected_add,
                'expected_sub': expected_sub,
                'source_line': cur.get('source_line')
            })
            prev_balance = bal
    return problems

def db_connect():
    if psycopg2 is None:
        return None
    try:
        return psycopg2.connect(
            host=os.getenv('DB_HOST','localhost'),
            database=os.getenv('DB_NAME','almsdata'),
            user=os.getenv('DB_USER','postgres'),
            password=os.getenv('DB_PASSWORD','***REDACTED***')
        )
    except Exception as e:
        print(f"[WARN] DB connection failed: {e}")
        return None

def reconcile_with_db(entries, account_number):
    conn = db_connect()
    if not conn:
        return {'db_unavailable': True}
    cur = conn.cursor()
    matched = []
    missing = []
    amount_mismatch = []
    duplicates = []

    for e in entries:
        if e['raw_amount'] is None:
            continue
        d = datetime.fromisoformat(e['date']).date()
        amt = e['raw_amount']
        # Query both debit and credit side for exact amount
        cur.execute("""
            SELECT transaction_id, description, debit_amount, credit_amount, balance
            FROM banking_transactions
            WHERE account_number = %s AND transaction_date = %s
              AND (
                 (debit_amount IS NOT NULL AND ABS(debit_amount - %s) < 0.01)
                 OR (credit_amount IS NOT NULL AND ABS(credit_amount - %s) < 0.01)
              )
        """, (account_number, d, amt, amt))
        rows = cur.fetchall()
        if not rows:
            missing.append(e)
            continue
        if len(rows) > 1:
            duplicates.append({'entry': e, 'rows': rows})
        # Attempt description match among results
        desc_lower = e['description'].lower()
        best = None
        for r in rows:
            db_desc = (r[1] or '').lower()
            if desc_lower == db_desc:
                best = r
                break
            # fuzzy: word overlap >= 2
            words_entry = set(desc_lower.split())
            words_db = set(db_desc.split())
            if len(words_entry & words_db) >= 2 and best is None:
                best = r
        if best is None:
            # take first
            best = rows[0]
        # Balance comparison if available
        bal_ok = True
        if e['balance'] is not None and best[4] is not None:
            if abs(e['balance'] - float(best[4])) > 0.01:
                bal_ok = False
                amount_mismatch.append({
                    'entry': e,
                    'db_row': best,
                    'db_balance': float(best[4])
                })
        matched.append({'entry': e, 'db_row': best, 'balance_match': bal_ok})

    cur.close(); conn.close()
    return {
        'matched': matched,
        'missing': missing,
        'amount_mismatch': amount_mismatch,
        'duplicates': duplicates
    }

def main():
    args = parse_args()
    lines = load_lines(args.input)
    lines = explode_multidate_lines(lines)
    year_hint = args.year

    entries = []
    segment_id = 0
    for line in lines:
        # Segment start detection
        if any(pat.match(line.strip()) for pat in SEGMENT_START_PATTERNS):
            segment_id += 1
            continue
        # Skip non-transaction summary lines
        if any(pat.match(line.strip()) for pat in SKIP_NON_TRANSACTION_PATTERNS):
            continue
        tx = classify_line(line, year_hint=year_hint)
        if tx:
            # Year enforcement filter
            if args.enforce_year and year_hint is not None:
                try:
                    if datetime.fromisoformat(tx['date']).year != year_hint:
                        continue
                except Exception:
                    pass
            tx['segment_id'] = segment_id
            entries.append(tx)
        if args.limit and len(entries) >= args.limit:
            break
        if args.verbose:
            print(f"[PARSE] {line} -> {tx}")

    balance_problems = running_balance_check(entries)
    reconciliation = reconcile_with_db(entries, args.account)

    summary = {
        'input': args.input,
        'year_hint': year_hint,
        'total_lines': len(lines),
        'parsed_entries': len(entries),
        'balance_problems': balance_problems,
        'reconciliation': {
            'matched': len(reconciliation.get('matched', [])),
            'missing': len(reconciliation.get('missing', [])),
            'amount_mismatch': len(reconciliation.get('amount_mismatch', [])),
            'duplicates': len(reconciliation.get('duplicates', [])),
            'db_unavailable': reconciliation.get('db_unavailable', False)
        }
    }

    print("\n=== SCOTIA STATEMENT PARSE SUMMARY ===")
    print(f"File: {args.input}")
    print(f"Lines read: {len(lines)}")
    print(f"Transactions parsed: {len(entries)}")
    print(f"Running balance issues: {len(balance_problems)}")
    unmatched_years = []
    if args.enforce_year and year_hint is not None:
        for e in entries:
            y = int(e['date'][:4])
            if y != year_hint:
                unmatched_years.append(y)
    if unmatched_years:
        print(f"[WARN] Entries with other years present despite enforcement: {sorted(set(unmatched_years))}")
    if balance_problems:
        for p in balance_problems[:10]:
            print(f"  LineIdx {p['index']} prev {p['prev_balance']} amount {p['amount']} current {p['balance']} (expected {p['expected_add']} or {p['expected_sub']})")
        if len(balance_problems) > 10:
            print(f"  ... {len(balance_problems)-10} more")
    print(f"Matched in DB: {summary['reconciliation']['matched']}")
    print(f"Missing in DB: {summary['reconciliation']['missing']}")
    print(f"Balance mismatches: {summary['reconciliation']['amount_mismatch']}")
    print(f"Potential duplicates: {summary['reconciliation']['duplicates']}")

    if args.output_json:
        out_path = args.output_json
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({
                'entries': entries,
                'balance_problems': balance_problems,
                'reconciliation_detail': reconciliation,
                'summary': summary
            }, f, indent=2)
        print(f"\n[WROTE] JSON report: {out_path}")

if __name__ == '__main__':
    main()
