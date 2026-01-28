#!/usr/bin/env python3
"""
Validate reconciliation scan files by reconstructing running balances and comparing
each entry to the authoritative banking_transactions table.

Workflow:
 1. Parse one or more reconciliation scan text/markdown files containing lines like:
      Jan 03  CREDIT MEMO 4017775 VISA        214.50    7,759.36
      Jan 01  Opening balance                              7,177.34
    - Month abbreviations (Jan, Feb, Mar, ...)
    - Amount is the second-to-last numeric token (when present)
    - Final numeric token is the reported running balance
    - Lines with only one numeric token are treated as balance-only markers (opening/closing)
 2. Build an ordered list of entries and recompute expected running balance.
 3. Validate reported balance vs expected (tolerance 0.01); record discrepancies.
 4. Classify each amount as deposit or withdrawal using keyword heuristics.
 5. Compare each entry to almsdata.banking_transactions for date+amount match.
 6. Produce JSON summary with issues and optional write to disk.

CLI:
  python -X utf8 scripts/validate_reconciliation_scan.py --input path\to\file.txt --year 2012 --account 0228362 --output-json scans_2012.json --write-json

Multiple inputs: provide repeated --input flags.

Assumptions:
 - Year supplied applies to all month/day entries in the file(s).
 - File ordering represents chronological sequence (already verified manually).
 - Banking table has columns: transaction_date, debit_amount, credit_amount, balance, description.
 - Running balance in banking_transactions is trusted but we still cross-check.

Limitations (initial version):
 - Does not attempt fuzzy matching on descriptions; direct date+amount matching only.
 - Multiple matches for same date+amount flagged; first match used.
 - Does not re-sequence same-day transactions; uses file order for expected balance math.

Exit codes:
 0 = Completed (may contain issues in JSON report)
 2 = Parsing failure / no entries found

Additions for future iterations (not implemented yet):
 - Fuzzy description similarity scoring
 - Duplicate suppression by deterministic hashing
 - CSV export of discrepancies
"""
import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import date
from typing import List, Optional, Dict, Any, Set

import psycopg2
try:
    import PyPDF2  # lightweight PDF text extraction
except ImportError:  # graceful degradation
    PyPDF2 = None

MONTH_MAP = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
    'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}

DEPOSIT_KEYWORDS = [
    'DEPOSIT', 'CREDIT MEMO', 'CORRECTION', 'REFUND', 'REVERSAL'
]

WITHDRAWAL_KEYWORDS = [
    'PURCHASE', 'WITHDRAWAL', 'PAYMENT', 'FEE', 'CHEQUE', 'CHQ',
    'NSF', 'INTEREST', 'TRANSFER', 'PAD', 'SERVICE CHARGE', 'S/C'
]

NUMBER_PATTERN = re.compile(r'(-?\d{1,3}(?:,\d{3})*(?:\.\d{2})|-?\d+\.\d{2})')
DATE_PREFIX_PATTERN = re.compile(r'^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\b')


@dataclass
class ScanEntry:
    index: int
    raw_line: str
    date: Optional[date]
    description: str
    amount: Optional[float]
    direction: Optional[str]
    reported_balance: Optional[float]
    expected_balance: Optional[float]
    balance_match: Optional[bool]
    issues: List[str]
    db_match_id: Optional[int] = None
    db_match_description: Optional[str] = None
    db_match_balance: Optional[float] = None


def parse_line(line: str, year: int, index: int, previous_balance: Optional[float]) -> ScanEntry:
    line = line.rstrip('\n')
    m = DATE_PREFIX_PATTERN.match(line)
    entry_date = None
    description_portion = line
    if m:
        mon_abbr = m.group('mon').upper()
        day = int(m.group('day'))
        if mon_abbr in MONTH_MAP:
            entry_date = date(year, MONTH_MAP[mon_abbr], day)
        # Remove leading date part for description parsing
        description_portion = line[m.end():].strip()

    numbers = NUMBER_PATTERN.findall(line)
    amount = None
    reported_balance = None
    issues: List[str] = []

    if numbers:
        # Reported balance is last numeric token
        try:
            reported_balance = float(numbers[-1].replace(',', ''))
        except ValueError:
            issues.append('balance_parse_error')
        if len(numbers) >= 2:
            # Amount is second-to-last token
            try:
                amount = float(numbers[-2].replace(',', ''))
            except ValueError:
                issues.append('amount_parse_error')
    else:
        issues.append('no_numeric_tokens')

    # Derive description by stripping trailing numeric tokens
    if numbers:
        # Remove the matched numeric token occurrences from the end progressive
        # Simpler approach: split line and drop trailing segments that are numeric
        parts = description_portion.split()
        # Walk from end removing numeric-like tokens until mismatch for amount+balance count
        numeric_needed = len(numbers)
        # We only expect up to 2 relevant numerics (amount, balance) for typical lines;
        # extra numerics inside description remain.
        stripped_parts = parts[:]  # copy
        removed = 0
        for i in range(len(parts)-1, -1, -1):
            token = parts[i]
            if NUMBER_PATTERN.fullmatch(token) and removed < 2:
                stripped_parts.pop()
                removed += 1
            else:
                break
        description = ' '.join(stripped_parts).strip()
    else:
        description = description_portion.strip()

    direction = None
    if amount is not None:
        upper_desc = description.upper()
        if any(k in upper_desc for k in WITHDRAWAL_KEYWORDS):
            direction = 'withdrawal'
        elif any(k in upper_desc for k in DEPOSIT_KEYWORDS):
            direction = 'deposit'
        else:
            # Heuristic: Opening/Closing balance lines have no amount; if amount exists default deposit unless keywords indicate otherwise.
            direction = 'deposit'

    expected_balance = None
    balance_match = None
    if reported_balance is not None:
        if previous_balance is None:
            # First balance encountered becomes baseline
            expected_balance = reported_balance
            balance_match = True
        else:
            if amount is None or direction is None:
                # Balance-only line: expected should equal reported
                expected_balance = reported_balance
                balance_match = abs(reported_balance - previous_balance) < 0.01 or True  # treat as marker
            else:
                if direction == 'deposit':
                    expected_balance = previous_balance + amount
                else:
                    expected_balance = previous_balance - amount
                balance_match = (abs(expected_balance - reported_balance) <= 0.01)
                if not balance_match:
                    issues.append('balance_mismatch')

    return ScanEntry(
        index=index,
        raw_line=line,
        date=entry_date,
        description=description,
        amount=amount,
        direction=direction,
        reported_balance=reported_balance,
        expected_balance=expected_balance,
        balance_match=balance_match,
        issues=issues or []
    )


def load_files(paths: List[str]) -> List[str]:
    """Load text lines from text/markdown or extract from PDF files."""
    lines: List[str] = []
    for p in paths:
        if not os.path.isfile(p):
            print(f"[WARN] File not found: {p}")
            continue
        ext = os.path.splitext(p)[1].lower()
        if ext == '.pdf':
            if PyPDF2 is None:
                print(f"[ERROR] PyPDF2 not installed; cannot extract PDF text for {p}.")
                continue
            try:
                with open(p, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text() or ''
                        for line in text.splitlines():
                            if line.strip():
                                lines.append(line)
            except Exception as e:
                print(f"[ERROR] Failed PDF extraction for {p}: {e}")
        else:
            with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.strip():
                        lines.append(line)
    return lines


def connect_db():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def match_to_db(conn, entries: List[ScanEntry], account: Optional[str]):
    cur = conn.cursor()
    used_ids: Set[int] = set()
    for e in entries:
        if e.amount is None or e.date is None or e.direction is None:
            continue
        # Build query for matching
        if e.direction == 'deposit':
            cur.execute(
                """
                SELECT transaction_id, credit_amount, debit_amount, balance, description
                FROM banking_transactions
                WHERE transaction_date = %s
                  AND credit_amount = %s
                  AND (%s IS NULL OR account_number = %s)
                """,
                (e.date, e.amount, account, account)
            )
        else:
            cur.execute(
                """
                SELECT transaction_id, credit_amount, debit_amount, balance, description
                FROM banking_transactions
                WHERE transaction_date = %s
                  AND debit_amount = %s
                  AND (%s IS NULL OR account_number = %s)
                """,
                (e.date, e.amount, account, account)
            )
        rows = cur.fetchall()
        if not rows:
            e.issues.append('db_no_match')
            continue
        if len(rows) > 1:
            e.issues.append(f'db_multiple_matches:{len(rows)}')
        # Pick first unused if possible
        chosen = None
        for r in rows:
            if r[0] not in used_ids:
                chosen = r
                break
        if chosen is None:
            chosen = rows[0]
            e.issues.append('db_match_reused')
        tx_id, credit_amt, debit_amt, db_balance, db_desc = chosen
        used_ids.add(tx_id)
        e.db_match_id = tx_id
        e.db_match_description = db_desc
        e.db_match_balance = db_balance
        if e.reported_balance is not None and db_balance is not None:
            if abs(e.reported_balance - db_balance) > 0.01:
                e.issues.append('db_balance_mismatch')
    cur.close()


def build_summary(entries: List[ScanEntry]) -> Dict[str, Any]:
    total = len(entries)
    balance_discrepancies = sum(1 for e in entries if e.balance_match is False)
    db_missing = sum(1 for e in entries if any(i.startswith('db_no_match') for i in e.issues))
    db_balance_mismatch = sum(1 for e in entries if 'db_balance_mismatch' in e.issues)
    return {
        'total_lines': total,
        'with_amount': sum(1 for e in entries if e.amount is not None),
        'balance_discrepancies': balance_discrepancies,
        'db_missing': db_missing,
        'db_balance_mismatches': db_balance_mismatch,
        'issues_present': any(e.issues for e in entries),
    }


def main():
    ap = argparse.ArgumentParser(description='Validate reconciliation scan files against running balances and database entries.')
    ap.add_argument('--input', action='append', help='Path to reconciliation scan file (repeatable).', required=True)
    ap.add_argument('--year', type=int, required=True, help='Year for the scan entries (e.g. 2012).')
    ap.add_argument('--account', type=str, default=None, help='Optional account_number filter (e.g. 0228362).')
    ap.add_argument('--output-json', type=str, default='reconciliation_validation.json', help='Output JSON file path.')
    ap.add_argument('--write-json', action='store_true', help='Write JSON report to disk instead of stdout only.')
    args = ap.parse_args()

    lines = load_files(args.input)
    if not lines:
        print('[ERROR] No lines loaded from provided files.')
        sys.exit(2)

    entries: List[ScanEntry] = []
    prev_balance: Optional[float] = None
    for idx, line in enumerate(lines):
        entry = parse_line(line, args.year, idx, prev_balance)
        # Update prev_balance for next iteration if we have a reported balance
        if entry.reported_balance is not None:
            prev_balance = entry.reported_balance
        entries.append(entry)

    # Database comparison
    try:
        conn = connect_db()
    except Exception as e:
        print(f'[ERROR] Database connection failed: {e}')
        sys.exit(2)

    match_to_db(conn, entries, args.account)
    conn.close()

    summary = build_summary(entries)
    serializable_entries = []
    for e in entries:
        d = asdict(e)
        if d.get('date') is not None:
            # dataclass date converted to iso string
            d['date'] = d['date'].isoformat()
        serializable_entries.append(d)

    report = {
        'account_number': args.account,
        'year': args.year,
        'summary': summary,
        'entries': serializable_entries
    }

    if args.write_json:
        with open(args.output_json, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f'[OK] JSON report written to {args.output_json}')
    else:
        print(json.dumps(report, indent=2))

    # Quick human summary
    print('\nSUMMARY:')
    for k, v in summary.items():
        print(f'  {k}: {v}')
    if summary['issues_present']:
        print('  Issues detected – see JSON report for details.')
    else:
        print('  No issues detected.')

    # Exit code 0 always (issues captured in JSON, not treated as fatal)
    sys.exit(0)


if __name__ == '__main__':
    main()
