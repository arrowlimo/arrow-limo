#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Match legacy LMS payment/reserve promo indicators to PostgreSQL charters.

Purpose:
- Extract LMS reserve/payment records (Access DB) for a target year (default 2012)
- Detect promo/trade/charity/etc. flags from LMS textual fields (e.g. payment type, notes, name markers)
- Match to PostgreSQL `charters` by reserve_number (or fallback heuristics)
- Produce a CSV mapping with classification and confidence level
- Optional: apply classifications into `charters.charter_data` and clean $0.01 marker payments

Safety:
- Default is dry-run, no DB writes.
- Requires --apply-classification flag to write JSON field updates.
- Requires --remove-penny-payments + --override-key to delete $0.01 payments (uses table_protection).

Heuristics:
- Payment type codes or descriptions containing: COMP, PROMO, TRADE, CHARITY, DONATION, FREE, FRIEND, WINNER
- Amount patterns: total paid 0, 0.01, or rate = 0 with non-cancelled status.
- Name tokens: 'Promo', 'Trade', 'Charity', 'Donation', 'Sponsor'

Outputs (reports/):
- lms_promo_flag_matches_{year}.csv
"""

import os
import sys
import csv
import argparse
import datetime as dt
from collections import defaultdict

try:
    import psycopg2
except Exception:
    print("ERROR: psycopg2 is required.", file=sys.stderr)
    sys.exit(2)

try:
    import pyodbc
except Exception:
    pyodbc = None

TABLE_PROTECTION_AVAILABLE = True
try:
    from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit
except Exception:
    TABLE_PROTECTION_AVAILABLE = False

PROMO_KEYWORDS = {
    'promo': ['promo', 'comp', 'complimentary', 'free', 'no charge', 'n/c'],
    'trade': ['trade', 'barter', 'exchange', 'in-kind', 'inkind'],
    'charity': ['charity', 'donation', 'fundraiser', 'sponsor'],
    'friend': ['friend', 'family', 'staff'],
    'winner': ['winner', 'raffle', 'contest', 'prize', 'draw'],
}


def db_connect_pg():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def connect_lms(path=None):
    if pyodbc is None:
        raise RuntimeError('pyodbc not installed; cannot read LMS Access DB')
    lms_path = path or os.getenv('LMS_PATH', r'L:\limo\lms.mdb')
    conn_str = f'DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};'
    return pyodbc.connect(conn_str)


def ensure_reports_dir():
    path = os.path.join(os.getcwd(), 'reports')
    os.makedirs(path, exist_ok=True)
    return path


def write_csv(path, rows, fieldnames):
    """Write a list of dict rows to CSV with provided field order."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def get_columns(pg_cur, table_name):
    pg_cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table_name,)
    )
    return {r[0] for r in pg_cur.fetchall()}


def detect_classification(text):
    if not text:
        return None, 0.0
    t = text.lower()
    for klass, words in PROMO_KEYWORDS.items():
        for w in words:
            if w in t:
                # Confidence heuristic: length of keyword vs text length
                conf = min(0.95, max(0.3, len(w) / max(len(t), 1)))
                return klass, conf
    return None, 0.0


def load_lms_reserves(lms_conn, year):
    cur = lms_conn.cursor()
    start = dt.date(year, 1, 1)
    end = dt.date(year, 12, 31)
    # Field names may differ; Reserve_No is the key
    cur.execute(
        """
        SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit, Pymt_Type, Vehicle, Name
        FROM Reserve
        WHERE PU_Date >= ? AND PU_Date <= ?
        ORDER BY PU_Date
        """,
        (start, end)
    )
    rows = []
    for r in cur.fetchall():
        (reserve_no, account_no, pu_date, rate, balance, deposit, pymt_type, vehicle, name) = r
        # Convert date types
        if isinstance(pu_date, dt.datetime):
            charter_date = pu_date.date()
        else:
            charter_date = pu_date
        text_blob = ' '.join(str(x) for x in [pymt_type, name] if x)
        klass, conf = detect_classification(text_blob)
        rows.append({
            'reserve_number': str(reserve_no).strip(),
            'account_number': account_no,
            'charter_date': charter_date,
            'rate': float(rate or 0),
            'balance': float(balance or 0),
            'deposit': float(deposit or 0),
            'pymt_type': pymt_type,
            'vehicle': vehicle,
            'client_name_lms': name,
            'lms_text': text_blob,
            'lms_promo_classification': klass,
            'lms_promo_confidence': conf,
        })
    return rows


def load_pg_charters(pg_cur, year):
    pg_cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, client_id, balance, deposit, booking_status, status,
               client_notes, booking_notes, notes, charter_data
        FROM charters
        WHERE charter_date >= %s AND charter_date <= %s
        ORDER BY charter_date
        """,
        (dt.date(year, 1, 1), dt.date(year, 12, 31))
    )
    rows = []
    for rec in pg_cur.fetchall():
        (cid, rn, cdate, client_id, balance, deposit, booking_status, status, cn, bn, n, cdata) = rec
        notes_blob = ' '.join(x for x in [cn, bn, n] if x)
        klass_notes, conf_notes = detect_classification(notes_blob)
        rows.append({
            'charter_id': cid,
            'reserve_number': rn.strip() if isinstance(rn, str) else str(rn) if rn is not None else None,
            'charter_date': cdate,
            'client_id': client_id,
            'balance': float(balance or 0),
            'deposit': float(deposit or 0),
            'booking_status': booking_status,
            'status': status,
            'notes_excerpt': notes_blob[:160] if notes_blob else None,
            'existing_classification': (cdata.get('free_classification') if isinstance(cdata, dict) else None) if cdata else None,
            'notes_classification': klass_notes,
            'notes_confidence': conf_notes,
        })
    return rows


def match_lms_to_pg(lms_rows, pg_rows):
    # Map charters by reserve_number
    pg_map = {}
    for r in pg_rows:
        key = r['reserve_number']
        if key:
            pg_map.setdefault(key, []).append(r)

    matches = []
    for l in lms_rows:
        rn = l['reserve_number']
        candidates = pg_map.get(rn, [])
        if not candidates:
            matches.append({
                'reserve_number': rn,
                'lms_charter_date': l['charter_date'],
                'pg_charter_id': None,
                'pg_charter_date': None,
                'lms_promo_classification': l['lms_promo_classification'],
                'lms_promo_confidence': l['lms_promo_confidence'],
                'existing_classification': None,
                'notes_classification': None,
                'notes_confidence': 0.0,
                'match_status': 'missing_in_pg'
            })
            continue
        # If multiple, pick earliest date diff
        pick = min(candidates, key=lambda c: abs((c['charter_date'] - l['charter_date']).days) if c['charter_date'] and l['charter_date'] else 9999)
        match_status = 'matched'
        matches.append({
            'reserve_number': rn,
            'lms_charter_date': l['charter_date'],
            'pg_charter_id': pick['charter_id'],
            'pg_charter_date': pick['charter_date'],
            'lms_promo_classification': l['lms_promo_classification'],
            'lms_promo_confidence': l['lms_promo_confidence'],
            'existing_classification': pick['existing_classification'],
            'notes_classification': pick['notes_classification'],
            'notes_confidence': pick['notes_confidence'],
            'match_status': match_status
        })
    return matches


def synthesize_final_class(row):
    # Prioritize existing classification, then LMS, then notes
    if row['existing_classification']:
        return row['existing_classification'], 'existing'
    if row['lms_promo_classification']:
        return row['lms_promo_classification'], 'lms'
    if row['notes_classification']:
        return row['notes_classification'], 'notes'
    return None, None


def apply_classifications(pg_cur, matches, override_key=None, remove_pennies=False):
    updated = 0
    deleted = 0
    softened = 0  # count of penny markers soft-removed due to FK constraints
    penny_fallback_rows = []  # details for audit CSV
    if remove_pennies and not TABLE_PROTECTION_AVAILABLE:
        raise RuntimeError('table_protection not available for payment deletion')
    if remove_pennies:
        protect_deletion('payments', dry_run=False, override_key=override_key)

    for m in matches:
        if m['match_status'] != 'matched':
            continue
        final_class, source = synthesize_final_class(m)
        if not final_class:
            continue
        pg_cur.execute(
            """
            UPDATE charters
            SET charter_data = COALESCE(charter_data::jsonb,'{}'::jsonb) || jsonb_build_object('free_classification', %s, 'classification_source', %s)
            WHERE charter_id = %s
            """,
            (final_class, source, m['pg_charter_id'])
        )
        updated += pg_cur.rowcount

        if remove_pennies:
            # Delete $0.01 payments linked to this charter (by charter_id or reserve_number)
            pg_cur.execute(
                """
                SELECT payment_id FROM payments
                WHERE (charter_id = %s OR reserve_number = %s)
                  AND ROUND(COALESCE(amount,payment_amount),2) = 0.01
                """,
                (m['pg_charter_id'], m['reserve_number'])
            )
            pids = [r[0] for r in pg_cur.fetchall()]
            if pids:
                try:
                    backup = create_backup_before_delete(pg_cur, 'payments', condition=f"payment_id IN ({','.join(str(x) for x in pids)})")
                except Exception as e:
                    if 'already exists' in str(e).lower():
                        backup = 'existing'
                    else:
                        raise
                # Soft-remove all marker payments to avoid FK conflicts
                pcols = get_columns(pg_cur, 'payments')
                has_notes = 'notes' in pcols
                try:
                    if has_notes:
                        pg_cur.execute(
                            f"UPDATE payments SET amount = 0, payment_amount = 0, notes = COALESCE(notes,'') || ' [MARKER ZEROED]' WHERE payment_id IN ({','.join(['%s']*len(pids))})",
                            tuple(pids)
                        )
                    else:
                        pg_cur.execute(
                            f"UPDATE payments SET amount = 0, payment_amount = 0 WHERE payment_id IN ({','.join(['%s']*len(pids))})",
                            tuple(pids)
                        )
                    softened += pg_cur.rowcount
                except Exception as e:
                    raise RuntimeError(f"Soft-remove UPDATE failed for payment_ids={pids}: {e}")
    return updated, deleted, softened, penny_fallback_rows


def main():
    parser = argparse.ArgumentParser(description='Match LMS promo flags to PostgreSQL charters.')
    parser.add_argument('--year', type=int, help='Single year to process.')
    parser.add_argument('--start-year', type=int, help='Start year for range.')
    parser.add_argument('--end-year', type=int, help='End year for range.')
    parser.add_argument('--lms-path', type=str, help='Path to lms.mdb Access file.')
    parser.add_argument('--write', action='store_true', help='Apply updates to PostgreSQL.')
    parser.add_argument('--apply-classification', action='store_true', help='Write classification into charters JSON.')
    parser.add_argument('--remove-penny-payments', action='store_true', help='Delete or soften $0.01 marker payments.')
    parser.add_argument('--override-key', type=str, default=None, help='Override key for protected payment deletions.')
    args = parser.parse_args()

    # Determine years to process
    if args.year:
        years = [args.year]
    elif args.start_year and args.end_year:
        if args.start_year > args.end_year:
            raise SystemExit('start-year must be <= end-year')
        years = list(range(args.start_year, args.end_year + 1))
    else:
        years = [2012]  # default

    reports_dir = ensure_reports_dir()

    pg_conn = None
    lms_conn = None
    try:
        pg_conn = db_connect_pg()
        pg_cur = pg_conn.cursor()
        lms_conn = connect_lms(args.lms_path)

        total_updated = 0
        total_deleted = 0
        total_softened = 0
        for year in years:
            lms_rows = load_lms_reserves(lms_conn, year)
            pg_rows = load_pg_charters(pg_cur, year)
            matches = match_lms_to_pg(lms_rows, pg_rows)

            # Add final synthesis columns
            for m in matches:
                fc, src = synthesize_final_class(m)
                m['final_classification'] = fc
                m['final_source'] = src

            csv_path = os.path.join(reports_dir, f'lms_promo_flag_matches_{year}.csv')
            write_csv(
                csv_path,
                matches,
                ['reserve_number','lms_charter_date','pg_charter_id','pg_charter_date','lms_promo_classification','lms_promo_confidence','existing_classification','notes_classification','notes_confidence','final_classification','final_source','match_status']
            )
            print(f"Wrote: {csv_path}")

            softened_rows = []
            if args.write and args.apply_classification:
                # Step 1: apply classifications only
                updated, _, _, _ = apply_classifications(
                    pg_cur, matches,
                    override_key=args.override_key,
                    remove_pennies=False
                )
                total_updated += updated
                pg_conn.commit()

                # Step 2: handle penny payments in separate transaction
                if args.remove_penny_payments:
                    try:
                        _, _, softened, fallback_rows = apply_classifications(
                            pg_cur, matches,
                            override_key=args.override_key,
                            remove_pennies=True
                        )
                        total_softened += softened
                        softened_rows = fallback_rows
                        pg_conn.commit()
                    except Exception as e:
                        # Rollback penny changes only, classifications remain committed
                        pg_conn.rollback()
                        # Collect all targeted payment_ids for audit to allow manual handling
                        # Recompute pids per charter
                        pg_cur2 = pg_conn.cursor()
                        all_pids = []
                        try:
                            for m in matches:
                                if m.get('match_status') != 'matched':
                                    continue
                                pg_cur2.execute(
                                    """
                                    SELECT payment_id FROM payments
                                    WHERE (charter_id = %s OR reserve_number = %s)
                                      AND ROUND(COALESCE(amount,payment_amount),2) = 0.01
                                    """,
                                    (m['pg_charter_id'], m['reserve_number'])
                                )
                                all_pids.extend([r[0] for r in pg_cur2.fetchall()])
                        except Exception:
                            pass
                        # De-duplicate and emit rows
                        softened_rows = [{'payment_id': pid, 'charter_id': None, 'reserve_number': None, 'error': str(e)} for pid in sorted(set(all_pids))]
                        print(f"Penny removal failed for {year}: {e}")

            # Write fallback penny audit if any
            if softened_rows:
                penny_csv = os.path.join(reports_dir, f'penny_payment_fallback_{year}.csv')
                write_csv(penny_csv, softened_rows, ['payment_id','charter_id','reserve_number','error'])
                print(f"Wrote (soft-removal audit): {penny_csv}")

        if args.write and args.apply_classification:
            print(f"APPLY summary (all years): classifications_updated={total_updated}, penny_payments_deleted={total_deleted}, penny_payments_softened={total_softened}")
        else:
            print("Dry-run only: no charter modifications applied.")

    except Exception as e:
        if pg_conn:
            pg_conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            if lms_conn:
                lms_conn.close()
        except Exception:
            pass
        try:
            if pg_conn:
                pg_conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
