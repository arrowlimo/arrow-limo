#!/usr/bin/env python3
"""
Auto-link payments to charters using #hint codes in payment notes.

Looks for patterns like "#019413" or "#19413" in payments.notes WHERE reserve_number IS NULL,
resolves to charters.reserve_number (zero-padded to 6 if necessary), and sets payments.charter_id
when there is a single unambiguous match.

Safety features:
- Dry-run by default. Use --apply to perform updates.
- Writes CSV logs for applied and skipped decisions.

Outputs (in l:/limo/reports):
- hint_link_applied.csv
- hint_link_skipped.csv
"""
import os
import re
import csv
import argparse
from typing import List, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

OUT_APPLIED = r"l:/limo/reports/hint_link_applied.csv"
OUT_SKIPPED = r"l:/limo/reports/hint_link_skipped.csv"


def extract_hint_numbers(text: str) -> List[str]:
    """Return list of numeric strings found after a #, e.g., '#1234' -> ['1234'].
    We ignore very short numbers (<3 digits) to reduce noise.
    """
    if not text:
        return []
    nums = re.findall(r"#(\d{3,7})", text)
    # Deduplicate preserving order
    seen = set()
    result = []
    for n in nums:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


def normalize_reserve_candidates(num: str) -> List[str]:
    """Generate candidate reserve_number strings from a raw number.
    e.g., '19413' -> ['019413', '19413']
    """
    if not num:
        return []
    candidates = [num]
    if len(num) < 6:
        candidates.insert(0, num.zfill(6))
    return candidates


def get_db_conn():
    load_dotenv('l:/limo/.env')
    load_dotenv()
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
        host=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', '5432')),
    )


def find_charter_for_reserve(cur, reserve_candidates: List[str]):
    if not reserve_candidates:
        return None
    # Try exact matches against reserve_number
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date
          FROM charters
         WHERE reserve_number = ANY(%s)
         ORDER BY charter_date DESC NULLS LAST
        """,
        (reserve_candidates,),
    )
    rows = cur.fetchall()
    if len(rows) == 1:
        return rows[0]
    # If multiple, prefer the one whose reserve_number equals the zero-padded first candidate
    if rows and len(reserve_candidates) > 0:
        preferred = reserve_candidates[0]
        exact = [r for r in rows if r['reserve_number'] == preferred]
        if len(exact) == 1:
            return exact[0]
    return None


def link_by_hints(apply: bool) -> Tuple[int, int]:
    os.makedirs('l:/limo/reports', exist_ok=True)
    applied_rows = []
    skipped_rows = []

    with get_db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT payment_id, payment_date, amount, payment_method, payment_key, notes
                  FROM payments
                 WHERE reserve_number IS NULL AND notes ~ '#[0-9]{3,7}'
                 ORDER BY payment_date DESC NULLS LAST, payment_id DESC
                """
            )
            candidates = cur.fetchall()

            for p in candidates:
                hints = extract_hint_numbers(p.get('notes') or '')
                if not hints:
                    skipped_rows.append({
                        'payment_id': p['payment_id'],
                        'reason': 'no_hint_found',
                        'notes': p.get('notes') or ''
                    })
                    continue

                linked = False
                for raw in hints:
                    reserve_candidates = normalize_reserve_candidates(raw)
                    charter = find_charter_for_reserve(cur, reserve_candidates)
                    if charter:
                        if apply:
                            try:
                                cur.execute(
                                    "UPDATE payments SET charter_id=%s, last_updated=NOW() WHERE payment_id=%s AND charter_id IS NULL",
                                    (charter['charter_id'], p['payment_id']),
                                )
                                applied_rows.append({
                                    'payment_id': p['payment_id'],
                                    'charter_id': charter['charter_id'],
                                    'reserve_number': charter['reserve_number'],
                                    'payment_date': p.get('payment_date'),
                                    'amount': float(p.get('amount') or 0),
                                    'method': p.get('payment_method'),
                                    'key': p.get('payment_key'),
                                    'hint_raw': raw,
                                })
                                linked = True
                                break
                            except Exception as e:
                                conn.rollback()
                                skipped_rows.append({
                                    'payment_id': p['payment_id'],
                                    'reason': f'db_error: {e}',
                                    'notes': p.get('notes') or ''
                                })
                                break
                        else:
                            applied_rows.append({
                                'payment_id': p['payment_id'],
                                'charter_id': charter['charter_id'],
                                'reserve_number': charter['reserve_number'],
                                'payment_date': p.get('payment_date'),
                                'amount': float(p.get('amount') or 0),
                                'method': p.get('payment_method'),
                                'key': p.get('payment_key'),
                                'hint_raw': raw,
                            })
                            linked = True
                            break

                if not linked:
                    skipped_rows.append({
                        'payment_id': p['payment_id'],
                        'reason': 'no_unique_charter_match',
                        'notes': p.get('notes') or ''
                    })

        # Commit only if apply mode
        if apply:
            conn.commit()

    # Write CSV outputs
    with open(OUT_APPLIED, 'w', newline='', encoding='utf-8') as f:
        if applied_rows:
            w = csv.DictWriter(f, fieldnames=list(applied_rows[0].keys()))
            w.writeheader(); w.writerows(applied_rows)
        else:
            f.write('')

    with open(OUT_SKIPPED, 'w', newline='', encoding='utf-8') as f:
        if skipped_rows:
            # Ensure consistent keys
            keys = set()
            for r in skipped_rows:
                keys.update(r.keys())
            w = csv.DictWriter(f, fieldnames=sorted(keys))
            w.writeheader(); w.writerows(skipped_rows)
        else:
            f.write('')

    return len(applied_rows), len(skipped_rows)


def main():
    parser = argparse.ArgumentParser(description='Auto-link payments to charters using #hints in notes')
    parser.add_argument('--apply', action='store_true', help='Apply updates to the database')
    args = parser.parse_args()

    applied, skipped = link_by_hints(apply=args.apply)
    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f"Hint linking complete [{mode}]: applied={applied}, skipped={skipped}")
    print(' ', OUT_APPLIED)
    print(' ', OUT_SKIPPED)


if __name__ == '__main__':
    main()
