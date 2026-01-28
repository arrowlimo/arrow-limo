#!/usr/bin/env python3
"""
Summarize reasons from legacy_match_links_skipped.csv and generate a detailed
conflicts CSV showing current DB link vs target legacy reservation mapping.

Outputs:
- l:/limo/reports/legacy_match_links_skipped_summary.csv (reason,count)
- l:/limo/reports/legacy_match_conflicts.csv (for already_linked_to_different_charter_*)
"""
import os
import csv
from collections import Counter

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

SKIPPED_CSV = r"l:/limo/reports/legacy_match_links_skipped.csv"
SUMMARY_CSV = r"l:/limo/reports/legacy_match_links_skipped_summary.csv"
CONFLICTS_CSV = r"l:/limo/reports/legacy_match_conflicts.csv"


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def main():
    if not os.path.exists(SKIPPED_CSV):
        print(f"Missing: {SKIPPED_CSV}. Run apply_legacy_reservation_matches.py first.")
        return

    os.makedirs(os.path.dirname(SUMMARY_CSV), exist_ok=True)

    # Summarize reasons
    reasons = Counter()
    rows = []
    with open(SKIPPED_CSV, 'r', newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            reasons[row.get('reason') or ''] += 1
            rows.append(row)

    with open(SUMMARY_CSV, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['reason','count'])
        for reason, count in reasons.most_common():
            w.writerow([reason, count])

    # Build conflicts file for already_linked_to_different_charter_* cases
    conflicts = [row for row in rows if row.get('reason','').startswith('already_linked_to_different_charter_')]
    if conflicts:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                out_rows = []
                for c in conflicts:
                    pid = int(c['payment_id'])
                    target_reserve = c['reserve_number']
                    cur.execute("SELECT charter_id FROM charters WHERE reserve_number=%s", (target_reserve,))
                    target = cur.fetchone()
                    target_charter_id = target['charter_id'] if target else None

                    cur.execute("""
                        SELECT p.payment_id, p.charter_id AS current_charter_id,
                               c.reserve_number AS current_reserve_number
                          FROM payments p
                     LEFT JOIN charters c ON c.charter_id = p.charter_id
                         WHERE p.payment_id = %s
                    """, (pid,))
                    db = cur.fetchone()
                    if db:
                        out_rows.append({
                            'payment_id': pid,
                            'current_charter_id': db['current_charter_id'],
                            'current_reserve_number': db['current_reserve_number'],
                            'target_reserve_number': target_reserve,
                            'target_charter_id': target_charter_id,
                        })

        with open(CONFLICTS_CSV, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=[
                'payment_id','current_charter_id','current_reserve_number','target_reserve_number','target_charter_id'
            ])
            w.writeheader()
            for r in out_rows:
                w.writerow(r)

    print(f"Wrote summary: {SUMMARY_CSV}")
    if conflicts:
        print(f"Wrote conflicts: {CONFLICTS_CSV} (rows: {len(conflicts)})")
    else:
        print("No conflicts found.")


if __name__ == '__main__':
    main()
