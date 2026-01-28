#!/usr/bin/env python3
"""
Row-by-row validation of screenshot-listed banking transactions against the DB.

Input CSV columns (fill from your screenshots):
- page (optional)
- line_no (optional)
- account_statement_format (optional; e.g., 00339-7461615). If omitted, we try --default-accounts.
- date (YYYY-MM-DD)
- amount (e.g., 1756.20)
- side (debit|credit|either) - 'either' will match either column
- description (optional; used as a hint only)

Example usage:
  # Generate a blank template to fill
  python -X utf8 scripts/validate_screenshot_rows.py --generate-template

  # Validate filled rows.csv, search both main CIBC accounts, ±3 days window
  python -X utf8 scripts/validate_screenshot_rows.py --input reports/screenshot_rows.csv --default-accounts 00339-7461615,3648117 --days 3 --exclude-zero

Output:
  - reports/screenshot_rows_validated.csv with match details
  - Summary printed to stdout
"""
import argparse
import csv
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Tuple, Optional

import psycopg2


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def find_account_by_statement_format(cur, statement_number: str) -> Tuple[Optional[str], Optional[str]]:
    cur.execute(
        """
        SELECT canonical_account_number, notes
        FROM account_number_aliases
        WHERE statement_format = %s
        """,
        (statement_number,),
    )
    row = cur.fetchone()
    if row:
        return row[0], row[1]
    # Fallback: maybe it's canonical already
    cur.execute("SELECT EXISTS (SELECT 1 FROM banking_transactions WHERE account_number = %s LIMIT 1)", (statement_number,))
    if cur.fetchone()[0]:
        return statement_number, '(assumed canonical)'
    return None, None


def tokenize(text: str) -> List[str]:
    if not text:
        return []
    # Basic tokenization: split on non-alnum, keep tokens length >= 4
    import re
    toks = re.split(r"[^A-Za-z0-9]+", text.upper())
    return [t for t in toks if len(t) >= 4]


def query_candidates(cur, account: str, target_date: date, amount: Decimal, side: str, days: int, exclude_zero: bool):
    start = target_date - timedelta(days=days)
    end = target_date + timedelta(days=days)
    where_amount = "( (debit_amount > 0 AND ABS(debit_amount - %s) < 0.01) OR (credit_amount > 0 AND ABS(credit_amount - %s) < 0.01) )"
    if side == 'debit':
        where_amount = "(debit_amount > 0 AND ABS(debit_amount - %s) < 0.01)"
    elif side == 'credit':
        where_amount = "(credit_amount > 0 AND ABS(credit_amount - %s) < 0.01)"

    extra = ""
    if exclude_zero:
        extra = "AND NOT (COALESCE(debit_amount,0)=0 AND COALESCE(credit_amount,0)=0)"

    sql = f"""
        SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, reconciliation_status, source_hash
        FROM banking_transactions
        WHERE account_number = %s
          AND transaction_date BETWEEN %s AND %s
          AND {where_amount}
          {extra}
        ORDER BY ABS(transaction_date - %s), transaction_id
    """
    # Amount bound needs two copies if we kept both sides
    if side == 'either':
        cur.execute(sql, (account, start, end, amount, amount, target_date))
    elif side == 'debit':
        cur.execute(sql, (account, start, end, amount, target_date))
    else:
        cur.execute(sql, (account, start, end, amount, target_date))
    return cur.fetchall()


def choose_best_match(candidates, target_date: date, descr_hint_tokens: List[str]):
    if not candidates:
        return None, 0
    # Score: smaller day diff better; then more token hits in description
    best = None
    best_score = (9999, -1)  # (abs_day_diff, token_hits)
    for row in candidates:
        tid, tdate, desc, deb, cred, status, shash = row
        day_diff = abs((tdate - target_date).days)
        token_hits = 0
        if descr_hint_tokens and desc:
            udesc = desc.upper()
            token_hits = sum(1 for t in descr_hint_tokens if t in udesc)
        score = (day_diff, -token_hits)
        if score < best_score:
            best_score = score
            best = row
    return best, len(candidates)


def generate_template(out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['page','line_no','account_statement_format','date','amount','side','description'])
        # Example rows (commented out for clarity)
        # w.writerow(['3','1','00339-7461615','2012-05-04','37.50','debit','CENTEX/DEERPARK'])
    print(f'📄 Row template created: {out_path}')


def validate_rows(input_csv: str, default_accounts: List[str], days: int, exclude_zero: bool, out_csv: str):
    conn = get_db_connection(); cur = conn.cursor()
    total = 0; matched = 0; multi = 0; not_found = 0

    with open(input_csv, 'r', encoding='utf-8') as f, open(out_csv, 'w', newline='', encoding='utf-8') as g:
        r = csv.DictReader(f)
        fieldnames = r.fieldnames + [
            'match_status','canonical_account','matched_transaction_id','matched_date','matched_side','day_diff','matched_description','matched_debit','matched_credit','reconciliation_status','source_hash','candidate_count'
        ]
        w = csv.DictWriter(g, fieldnames=fieldnames)
        w.writeheader()

        for row in r:
            total += 1
            page = (row.get('page') or '').strip()
            line_no = (row.get('line_no') or '').strip()
            stmt = (row.get('account_statement_format') or '').strip()
            date_s = (row.get('date') or '').strip()
            amount_s = (row.get('amount') or '').strip()
            side = (row.get('side') or 'either').strip().lower()
            descr = (row.get('description') or '').strip()

            if not date_s or not amount_s:
                row['match_status'] = 'SKIPPED_MISSING_FIELDS'
                w.writerow(row); continue

            tdate = date.fromisoformat(date_s)
            amount = Decimal(amount_s)
            hint_tokens = tokenize(descr)

            # Resolve accounts to search
            accounts_to_search = []
            # Always try the row's account first (if provided)
            if stmt:
                canon, _ = find_account_by_statement_format(cur, stmt)
                if canon:
                    accounts_to_search.append(canon)
            # Also append defaults to catch mis-filed or cross-account postings
            for s in default_accounts:
                canon, _ = find_account_by_statement_format(cur, s)
                if canon:
                    accounts_to_search.append(canon)
            # Dedupe while preserving order
            seen = set(); ordered = []
            for a in accounts_to_search:
                if a not in seen:
                    seen.add(a); ordered.append(a)
            accounts_to_search = ordered

            best_overall = None
            best_overall_count = 0
            best_overall_account = None

            for acct in accounts_to_search:
                # First pass: honor requested side; if nothing, retry with 'either'
                search_side = side if side in ('debit','credit') else 'either'
                cands = query_candidates(cur, acct, tdate, amount, search_side, days, exclude_zero)
                pick, cand_count = choose_best_match(cands, tdate, hint_tokens)
                if pick is None and search_side != 'either':
                    cands = query_candidates(cur, acct, tdate, amount, 'either', days, exclude_zero)
                    pick, cand_count = choose_best_match(cands, tdate, hint_tokens)
                if pick is None:
                    continue
                # Choose the match with smallest day diff, then most token hits
                if best_overall is None:
                    best_overall, best_overall_count, best_overall_account = pick, cand_count, acct
                else:
                    # Compare by day diff first
                    cur_day_diff = abs((pick[1] - tdate).days)
                    best_day_diff = abs((best_overall[1] - tdate).days)
                    if cur_day_diff < best_day_diff:
                        best_overall, best_overall_count, best_overall_account = pick, cand_count, acct

            if best_overall is None:
                row.update({
                    'match_status':'NOT_FOUND', 'canonical_account':'', 'matched_transaction_id':'', 'matched_date':'', 'matched_side':'', 'day_diff':'', 'matched_description':'', 'matched_debit':'', 'matched_credit':'', 'reconciliation_status':'', 'source_hash':'', 'candidate_count':'0'
                })
                not_found += 1
                w.writerow(row); continue

            tid, tdate2, desc2, deb2, cred2, rstatus, shash = best_overall
            day_diff = (tdate2 - tdate).days
            mside = 'debit' if (deb2 or Decimal('0')) > 0 else 'credit'

            status_label = 'MATCH'
            if best_overall_count > 1:
                status_label = 'CANDIDATE_MULTI'
                multi += 1
            else:
                matched += 1

            row.update({
                'match_status': status_label,
                'canonical_account': best_overall_account,
                'matched_transaction_id': str(tid),
                'matched_date': tdate2.isoformat(),
                'matched_side': mside,
                'day_diff': str(day_diff),
                'matched_description': (desc2 or '')[:120],
                'matched_debit': f'{(deb2 or Decimal("0")):.2f}',
                'matched_credit': f'{(cred2 or Decimal("0")):.2f}',
                'reconciliation_status': rstatus or '',
                'source_hash': shash or '',
                'candidate_count': str(best_overall_count),
            })
            w.writerow(row)

    print('Validation summary:')
    print(f'  Total rows: {total}')
    print(f'  Matches: {matched}')
    print(f'  Multi-candidates: {multi}')
    print(f'  Not found: {not_found}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', type=str, default=None, help='CSV of screenshot rows to validate')
    ap.add_argument('--default-accounts', type=str, default='00339-7461615,3648117', help='Comma-separated statement formats to search when a row has no account specified')
    ap.add_argument('--days', type=int, default=3, help='Posting lag window in days (±)')
    ap.add_argument('--exclude-zero', action='store_true', help='Exclude DB rows where both debit and credit are zero')
    ap.add_argument('--generate-template', action='store_true', help='Write a blank template CSV to reports/')
    args = ap.parse_args()

    reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'reports'))
    os.makedirs(reports_dir, exist_ok=True)

    if args.generate_template:
        generate_template(os.path.join(reports_dir, 'screenshot_rows_template.csv'))

    if args.input:
        out_csv = os.path.join(reports_dir, 'screenshot_rows_validated.csv')
        defaults = [x.strip() for x in args.default_accounts.split(',') if x.strip()]
        # Python identifiers cannot contain '-', so parse manually
        defaults = [x for x in defaults if x]
        validate_rows(args.input, defaults, args.days, args.exclude_zero, out_csv)


if __name__ == '__main__':
    main()
