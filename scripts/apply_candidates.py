#!/usr/bin/env python3
"""
Apply high-confidence candidate links from reports/unlinked_payment_link_candidates.csv.

Linking rules (strict, safe):
- Only link when there is exactly one candidate for a payment meeting ALL of:
  - candidate_match_type == 'amount_date'
  - abs(candidate_total_amount_due - payment.amount) <= 0.01 (or configured tolerance)
  - |candidate_charter_date - payment_date| <= 1 day
  - charter is not placeholder (if column exists)

Outputs:
- l:/limo/reports/candidate_links_applied.csv
- l:/limo/reports/candidate_links_skipped.csv
"""
import os
import csv
import argparse
from datetime import datetime
from collections import defaultdict

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

CANDIDATES_CSV = r"l:/limo/reports/unlinked_payment_link_candidates.csv"
OUT_APPLIED = r"l:/limo/reports/candidate_links_applied.csv"
OUT_SKIPPED = r"l:/limo/reports/candidate_links_skipped.csv"

AMOUNT_EPS = float(os.getenv('APPLY_CANDIDATES_AMOUNT_EPS', '0.01'))
DATE_WINDOW_DAYS = int(os.getenv('APPLY_CANDIDATES_DATE_WINDOW_DAYS', '1'))


def get_conn():
    load_dotenv('l:/limo/.env'); load_dotenv()
    return psycopg2.connect(
        dbname=os.getenv('DB_NAME','almsdata'),
        user=os.getenv('DB_USER','postgres'),
        password=os.getenv('DB_PASSWORD','***REMOVED***'),
        host=os.getenv('DB_HOST','localhost'),
        port=int(os.getenv('DB_PORT','5432')),
    )


def parse_date(d):
    if not d:
        return None
    if isinstance(d, datetime):
        return d.date()
    try:
        return datetime.fromisoformat(str(d)).date()
    except Exception:
        try:
            return datetime.strptime(str(d), "%Y-%m-%d").date()
        except Exception:
            return None


def main():
    parser = argparse.ArgumentParser(description='Apply high-confidence candidate links')
    parser.add_argument('--apply', action='store_true', help='Apply updates (otherwise dry-run)')
    args = parser.parse_args()

    if not os.path.exists(CANDIDATES_CSV):
        print('Candidates CSV not found:', CANDIDATES_CSV)
        return

    # Group candidates by payment_id
    by_payment = defaultdict(list)
    with open(CANDIDATES_CSV, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            pid = row.get('payment_id')
            if not pid:
                continue
            by_payment[pid].append(row)

    applied = []
    skipped = []

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Detect placeholder column
            cur.execute("""
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.columns
                  WHERE table_schema='public' AND table_name='charters' AND column_name='is_placeholder'
                ) AS has
            """)
            has_placeholder = cur.fetchone()['has']

            for pid, cands in by_payment.items():
                # Filter to amount_date only
                filtered = [c for c in cands if (c.get('candidate_match_type') or '') == 'amount_date']
                if not filtered:
                    skipped.append({'payment_id': pid, 'reason': 'no_amount_date_candidates'})
                    continue

                # normalize fields and apply strict rules
                strong = []
                for c in filtered:
                    try:
                        p_amt = float(c.get('amount') or 0)
                        due = float(c.get('candidate_total_amount_due') or 0)
                        if abs(p_amt - due) > AMOUNT_EPS:
                            continue
                        p_date = parse_date(c.get('payment_date'))
                        ch_date = parse_date(c.get('candidate_charter_date'))
                        if not p_date or not ch_date:
                            continue
                        if abs((ch_date - p_date).days) > DATE_WINDOW_DAYS:
                            continue
                        strong.append(c)
                    except Exception:
                        continue

                if len(strong) != 1:
                    skipped.append({'payment_id': pid, 'reason': f'strong_candidates={len(strong)}'})
                    continue

                c = strong[0]
                charter_id = c.get('candidate_charter_id')
                if not charter_id:
                    skipped.append({'payment_id': pid, 'reason': 'missing_charter_id'})
                    continue

                # Exclude placeholders if present
                if has_placeholder:
                    cur.execute("SELECT is_placeholder FROM charters WHERE charter_id=%s", (charter_id,))
                    row = cur.fetchone()
                    if row and row.get('is_placeholder'):
                        skipped.append({'payment_id': pid, 'reason': 'placeholder_charter'})
                        continue

                if args.apply:
                    try:
                        cur.execute(
                            "UPDATE payments SET charter_id=%s, last_updated=NOW() WHERE payment_id=%s AND charter_id IS NULL",
                            (charter_id, pid)
                        )
                        if cur.rowcount:
                            applied.append({
                                'payment_id': pid,
                                'charter_id': charter_id,
                                'reserve_number': c.get('candidate_reserve_number'),
                                'payment_date': c.get('payment_date'),
                                'amount': c.get('amount'),
                                'source': c.get('source'),
                            })
                        else:
                            skipped.append({'payment_id': pid, 'reason': 'not_updated'})
                    except Exception as e:
                        conn.rollback()
                        skipped.append({'payment_id': pid, 'reason': f'db_error: {e}'})
                else:
                    applied.append({
                        'payment_id': pid,
                        'charter_id': charter_id,
                        'reserve_number': c.get('candidate_reserve_number'),
                        'payment_date': c.get('payment_date'),
                        'amount': c.get('amount'),
                        'source': c.get('source'),
                    })

        if args.apply:
            conn.commit()

    os.makedirs('l:/limo/reports', exist_ok=True)
    with open(OUT_APPLIED, 'w', newline='', encoding='utf-8') as f:
        if applied:
            w = csv.DictWriter(f, fieldnames=list(applied[0].keys()))
            w.writeheader(); w.writerows(applied)
        else:
            f.write('')
    with open(OUT_SKIPPED, 'w', newline='', encoding='utf-8') as f:
        if skipped:
            # normalize headers
            keys = set()
            for s in skipped:
                keys.update(s.keys())
            w = csv.DictWriter(f, fieldnames=sorted(keys))
            w.writeheader(); w.writerows(skipped)
        else:
            f.write('')

    print(f"Candidate linking complete [{'APPLY' if args.apply else 'DRY-RUN'}]: applied={len(applied)}, skipped={len(skipped)}")
    print(' ', OUT_APPLIED)
    print(' ', OUT_SKIPPED)


if __name__ == '__main__':
    main()
