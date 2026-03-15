#!/usr/bin/env python3
"""
Apply legacy reservation matches to link payments → charters using
docs/oldalms/new_alms/limo backup/RESERVATION-MATCHES-SUMMARY.csv.

Rules (safe-by-default):
- For each CSV row, take ReservationNumber → find charters.charter_id.
- Find payments.payment_id == CSV PaymentId.
- Only set payments.charter_id when:
  - payment exists, and
  - charter exists, and
  - payment.charter_id is NULL (or matches the same charter_id), and
  - PaymentId appears only once in the CSV (to avoid multi-charter ambiguity here).

Outputs (to l:/limo/reports/):
- legacy_match_links_applied.csv
- legacy_match_links_skipped.csv (with reason)

Usage:
  python scripts/apply_legacy_reservation_matches.py           # dry-run
  python scripts/apply_legacy_reservation_matches.py --apply   # apply updates
"""
import os
import csv
import argparse
from collections import defaultdict
from typing import Dict, Any, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv


# Load env (workspace .env first, then process env)
load_dotenv('l:/limo/.env'); load_dotenv()

DB_HOST = os.getenv('DB_HOST','localhost')
DB_PORT = int(os.getenv('DB_PORT','5432'))
DB_NAME = os.getenv('DB_NAME','almsdata')
DB_USER = os.getenv('DB_USER','postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD','')

CSV_IN = r"l:/limo/docs/oldalms/new_alms/limo backup/RESERVATION-MATCHES-SUMMARY.csv"
OUT_APPLIED = r"l:/limo/reports/legacy_match_links_applied.csv"
OUT_SKIPPED = r"l:/limo/reports/legacy_match_links_skipped.csv"


def get_conn():
    return psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)


def normalize_reserve_number(s: str) -> str:
    s = (s or '').strip()
    # Keep digits only, left-pad to 6 when length is between 3 and 6
    digits = ''.join(ch for ch in s if ch.isdigit())
    if not digits:
        return ''
    if len(digits) < 6:
        digits = digits.zfill(6)
    return digits


def read_legacy_csv(path: str) -> Tuple[list[Dict[str, Any]], Dict[str, int]]:
    rows = []
    by_payment_id = defaultdict(int)
    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            pid_raw = (r.get('PaymentId') or '').strip().strip('"')
            res_raw = (r.get('ReservationNumber') or '').strip().strip('"')
            if not pid_raw or not res_raw:
                continue
            try:
                pid = int(pid_raw)
            except Exception:
                # Non-integer PaymentId; skip
                continue
            reserve_number = normalize_reserve_number(res_raw)
            if not reserve_number:
                continue
            rows.append({
                'payment_id': pid,
                'reserve_number': reserve_number,
                'raw': r,
            })
            by_payment_id[pid] += 1
    return rows, by_payment_id


def main():
    ap = argparse.ArgumentParser(description='Apply legacy reservation matches to payments.charter_id (safe-by-default)')
    ap.add_argument('--apply', action='store_true', help='Apply changes (otherwise dry-run)')
    ap.add_argument('--csv', default=CSV_IN, help='Path to RESERVATION-MATCHES-SUMMARY.csv')
    ap.add_argument('--allow-same-target-duplicates', action='store_true',
                   help='Allow linking when the same PaymentId appears multiple times but all map to the same reserve_number')
    ap.add_argument('--allow-safe-overrides', action='store_true',
                   help='Allow overriding existing links only if amount/date favor the legacy target (<=$0.01 and <=1 day)')
    args = ap.parse_args()

    if not os.path.exists(args.csv):
        print(f"CSV not found: {args.csv}")
        return

    os.makedirs(os.path.dirname(OUT_APPLIED), exist_ok=True)

    legacy_rows, dup_counts = read_legacy_csv(args.csv)
    print(f"Loaded legacy rows: {len(legacy_rows)} (unique payment_ids: {len(set(r['payment_id'] for r in legacy_rows))})")

    applied = []
    skipped = []

    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Precompute duplicate PaymentId → set of reserve_numbers
            dup_targets = {}
            for pid, count in dup_counts.items():
                if count > 1:
                    targets = {row['reserve_number'] for row in legacy_rows if row['payment_id'] == pid}
                    dup_targets[pid] = targets

            for r in legacy_rows:
                pid = r['payment_id']
                reserve_number = r['reserve_number']

                # Skip if this payment_id appears multiple times in legacy CSV (likely multi-charter allocation)
                if dup_counts[pid] > 1:
                    targets = dup_targets.get(pid, set())
                    if args.allow_same_target_duplicates and len(targets) == 1 and reserve_number in targets:
                        # Treat as benign duplicate - proceed
                        pass
                    else:
                        skipped.append({'payment_id': pid, 'reserve_number': reserve_number, 'reason': 'duplicate_payment_id_in_legacy_csv'})
                        continue

                # Find charter by reserve_number
                cur.execute("SELECT charter_id FROM charters WHERE reserve_number = %s", (reserve_number,))
                ch = cur.fetchone()
                if not ch:
                    skipped.append({'payment_id': pid, 'reserve_number': reserve_number, 'reason': 'reserve_not_found'})
                    continue
                charter_id = ch['charter_id']

                # Find payment by payment_id
                cur.execute("SELECT payment_id, charter_id FROM payments WHERE payment_id = %s", (pid,))
                p = cur.fetchone()
                if not p:
                    skipped.append({'payment_id': pid, 'reserve_number': reserve_number, 'reason': 'payment_not_found'})
                    continue

                existing = p['charter_id']
                if existing and existing != charter_id:
                    # Consider safe override rules if enabled
                    if not args.allow_safe_overrides:
                        skipped.append({'payment_id': pid, 'reserve_number': reserve_number, 'reason': f'already_linked_to_different_charter_{existing}'})
                        continue

                    # Load payment + both target and current charter details for comparison
                    cur.execute("SELECT amount, payment_date FROM payments WHERE payment_id=%s", (pid,))
                    pay = cur.fetchone()
                    cur.execute("SELECT charter_id, total_amount_due, charter_date FROM charters WHERE charter_id=%s", (charter_id,))
                    tgt = cur.fetchone()
                    cur.execute("SELECT charter_id, total_amount_due, charter_date FROM charters WHERE charter_id=%s", (existing,))
                    curr = cur.fetchone()

                    def safe_match(charter):
                        try:
                            amt_ok = abs(float(pay['amount']) - float(charter['total_amount_due'] or 0)) <= 0.01
                            date_ok = pay['payment_date'] is not None and charter['charter_date'] is not None and abs((pay['payment_date'] - charter['charter_date']).days) <= 1
                            return amt_ok and date_ok
                        except Exception:
                            return False

                    target_ok = tgt and safe_match(tgt)
                    current_ok = curr and safe_match(curr)

                    # Only override if target matches and current does not
                    if not target_ok or current_ok:
                        reason = 'safe_override_rejected_target_mismatch' if not target_ok else 'safe_override_rejected_current_also_matches'
                        skipped.append({'payment_id': pid, 'reserve_number': reserve_number, 'reason': reason})
                        continue

                if existing == charter_id:
                    skipped.append({'payment_id': pid, 'reserve_number': reserve_number, 'reason': 'already_linked_same_charter'})
                    continue

                # Ready to link
                if args.apply:
                    cur.execute(
                        "UPDATE payments SET charter_id=%s, last_updated=NOW() WHERE payment_id=%s AND (charter_id IS NULL OR charter_id=%s)",
                        (charter_id, pid, charter_id)
                    )
                    if cur.rowcount == 1:
                        applied.append({'payment_id': pid, 'charter_id': charter_id, 'reserve_number': reserve_number, 'status': 'updated'})
                    else:
                        skipped.append({'payment_id': pid, 'reserve_number': reserve_number, 'reason': 'update_noop'})
                else:
                    # Dry-run preview
                    applied.append({'payment_id': pid, 'charter_id': charter_id, 'reserve_number': reserve_number, 'status': 'would_update'})

    # Write outputs
    with open(OUT_APPLIED, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['payment_id','charter_id','reserve_number','status'])
        w.writeheader()
        for a in applied:
            w.writerow(a)

    with open(OUT_SKIPPED, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['payment_id','reserve_number','reason'])
        w.writeheader()
        for s in skipped:
            w.writerow(s)

    print(f"Legacy match linking complete {'[APPLY]' if args.apply else '[DRY-RUN]'}: applied={len(applied)}, skipped={len(skipped)}")
    print('Applied CSV:', OUT_APPLIED)
    print('Skipped CSV:', OUT_SKIPPED)


if __name__ == '__main__':
    main()
