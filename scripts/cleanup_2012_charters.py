#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cleanup 2012 charters with the following workflow:

1) Identify charters paid $0.01 (used historically to mark promo/trade/charity)
   - Inspect charter notes to infer classification (promo/trade/charity/friend/winner/etc.)
   - Dry-run report with proposed classification
   - Optional: apply classification to charters.charter_data JSON
   - Optional: remove the $0.01 payment rows (requires override key + backups)

2) Cancelled charters with balances: list for review

3) Uncollectible candidates (open balance, aged):
   - Dry-run report; optional prepare/write-off entries via negative charter_charges (if table exists)

4) Missing driver assignment for 2012:
   - Suggest driver based on exact name match (charters.driver_name ↔ employees.full_name)
   - Fallback: match via driver_payroll charter_id/reserve_number if available
   - Optional: apply high-confidence updates

Safety:
- Defaults to dry-run with CSV outputs in reports/
- Uses table_protection for any deletion from protected tables (payments)
- Schema introspection for optional columns/tables
"""

import os
import re
import sys
import csv
import argparse
import datetime as dt
from collections import defaultdict

try:
    import psycopg2
except Exception as e:
    print("ERROR: psycopg2 is required.", file=sys.stderr)
    sys.exit(2)

TABLE_PROTECTION_AVAILABLE = True
try:
    from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit
except Exception:
    TABLE_PROTECTION_AVAILABLE = False


YEAR = 2012


def db_connect():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    port = int(os.getenv('DB_PORT', '5432'))
    return psycopg2.connect(host=host, dbname=name, user=user, password=password, port=port)


def get_columns(cur, table_name):
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,)
    )
    cols = {}
    for c, t in cur.fetchall():
        cols[c] = t
    return cols


def ensure_reports_dir():
    path = os.path.join(os.getcwd(), 'reports')
    os.makedirs(path, exist_ok=True)
    return path


KEYWORDS = {
    'promo': ['promo', 'promotion', 'complimentary', 'comp', 'free ride', 'free of charge', 'no charge'],
    'trade': ['trade', 'in-kind', 'inkind', 'in kind', 'barter', 'exchange'],
    'charity': ['charity', 'donation', 'fundraiser', 'fund raising', 'sponsorship', 'sponsor'],
    'friend': ['friend', 'freind', 'family', 'relative'],
    'winner': ['winner', 'raffle', 'draw', 'contest', 'prize'],
}


def detect_classification(text):
    if not text:
        return None
    t = text.lower()
    for klass, words in KEYWORDS.items():
        for w in words:
            if w in t:
                return klass
    return None


def fetch_penny_marked(cur):
    # Sum payments per charter for 2012 and pick those totaling exactly 0.01
    cur.execute(
        """
        WITH p AS (
            SELECT 
                COALESCE(charter_id, NULL) AS charter_id,
                reserve_number,
                ROUND(SUM(COALESCE(amount, payment_amount)), 2) AS total_paid,
                array_agg(payment_id) AS payment_ids
            FROM payments
            WHERE (payment_date >= %s AND payment_date <= %s)
            GROUP BY charter_id, reserve_number
        )
        SELECT c.charter_id, c.reserve_number, c.charter_date, c.client_id, c.booking_status, c.status,
               c.client_notes, c.booking_notes, c.notes,
               p.total_paid, p.payment_ids
        FROM charters c
        JOIN p ON (p.charter_id = c.charter_id OR (p.charter_id IS NULL AND p.reserve_number = c.reserve_number))
        WHERE c.charter_date >= %s AND c.charter_date <= %s
          AND p.total_paid = 0.01
        ORDER BY c.charter_date, c.reserve_number
        """,
        (dt.date(YEAR, 1, 1), dt.date(YEAR, 12, 31), dt.date(YEAR, 1, 1), dt.date(YEAR, 12, 31))
    )
    rows = []
    for charter_id, reserve_number, cdate, client_id, booking_status, status, client_notes, booking_notes, notes, total_paid, payment_ids in cur.fetchall():
        text = ' '.join([x for x in [client_notes, booking_notes, notes] if x])
        classification = detect_classification(text)
        rows.append({
            'charter_id': charter_id,
            'reserve_number': reserve_number,
            'charter_date': cdate,
            'client_id': client_id,
            'booking_status': booking_status,
            'status': status,
            'notes_excerpt': (text[:200] + '...') if text and len(text) > 200 else text,
            'proposed_classification': classification or 'review',
            'payment_ids': payment_ids,
        })
    return rows


def apply_classification_and_remove_pennies(cur, rows, override_key, apply_classification=False, remove_payments=False):
    updated = 0
    deleted = 0

    if remove_payments:
        if not TABLE_PROTECTION_AVAILABLE:
            raise RuntimeError('table_protection module not available; cannot delete from payments safely')
        protect_deletion('payments', dry_run=False, override_key=override_key)

    # Schema for JSON updates
    ccols = get_columns(cur, 'charters')
    has_charter_data = 'charter_data' in ccols

    for r in rows:
        cid = r['charter_id']
        klass = r['proposed_classification']

        if apply_classification and has_charter_data and klass and klass != 'review':
            # Merge JSON tag
            cur.execute(
                """
                UPDATE charters
                SET charter_data = COALESCE(charter_data::jsonb, '{}'::jsonb) ||
                    jsonb_build_object('free_classification', %s, 'free_marked_via_payment', true)
                WHERE charter_id = %s
                """,
                (klass, cid)
            )
            updated += cur.rowcount

        if remove_payments and r['payment_ids']:
            # Backup then delete those payments
            backup_name = create_backup_before_delete(cur, 'payments', condition=f"payment_id IN ({','.join(str(pid) for pid in r['payment_ids'])})")
            cur.execute(
                f"DELETE FROM payments WHERE payment_id IN ({','.join(['%s']*len(r['payment_ids']))})",
                tuple(r['payment_ids'])
            )
            deleted += cur.rowcount
            log_deletion_audit('payments', cur.rowcount, condition=f"payment_id IN ({','.join(str(pid) for pid in r['payment_ids'])}); backup={backup_name}")

    return updated, deleted


def fetch_cancelled_with_balance(cur):
    # cancelled flag/booking_status may vary; check both
    ccols = get_columns(cur, 'charters')
    cancelled_col = 'cancelled' if 'cancelled' in ccols else None
    balance_col = 'balance' if 'balance' in ccols else None

    where_bits = ["charter_date >= %s", "charter_date <= %s"]
    params = [dt.date(YEAR, 1, 1), dt.date(YEAR, 12, 31)]
    if cancelled_col:
        where_bits.append(f"COALESCE({cancelled_col}, false) = true")
    else:
        if 'booking_status' in ccols:
            where_bits.append("LOWER(COALESCE(booking_status,'')) LIKE '%cancel%'")

    if balance_col:
        where_bits.append("COALESCE(balance,0) > 0.009")

    cur.execute(
        f"""
        SELECT charter_id, reserve_number, charter_date, client_id, COALESCE(balance,0) AS balance,
               client_notes, booking_notes, notes
        FROM charters
        WHERE {' AND '.join(where_bits)}
        ORDER BY charter_date, reserve_number
        """,
        tuple(params)
    )
    rows = []
    for rec in cur.fetchall():
        cid, rn, cdate, client_id, bal, cn, bn, n = rec
        rows.append({
            'charter_id': cid,
            'reserve_number': rn,
            'charter_date': cdate,
            'client_id': client_id,
            'balance': float(bal or 0),
            'notes_excerpt': ' '.join(x for x in [cn, bn, n] if x)[:200]
        })
    return rows


def fetch_uncollectible_candidates(cur, min_days_overdue=120):
    # Heuristic: open balance and older than threshold, not cancelled
    ccols = get_columns(cur, 'charters')
    balance_expr = 'COALESCE(balance,0)'
    cancelled_pred = 'COALESCE(cancelled,false) = false' if 'cancelled' in ccols else "(booking_status IS NULL OR LOWER(booking_status) NOT LIKE '%cancel%')"

    cur.execute(
        f"""
        SELECT charter_id, reserve_number, charter_date, {balance_expr} AS balance,
               client_id, client_notes, booking_notes, notes
        FROM charters
        WHERE charter_date >= %s AND charter_date <= %s
          AND {balance_expr} > 0.009 AND {cancelled_pred}
        ORDER BY charter_date
        """,
        (dt.date(YEAR, 1, 1), dt.date(YEAR, 12, 31))
    )
    today = dt.date.today()
    out = []
    for cid, rn, cdate, bal, client_id, cn, bn, n in cur.fetchall():
        age_days = (today - (cdate if isinstance(cdate, dt.date) else cdate.date())).days
        if age_days >= min_days_overdue:
            out.append({
                'charter_id': cid,
                'reserve_number': rn,
                'charter_date': cdate,
                'age_days': age_days,
                'balance': float(bal or 0),
                'client_id': client_id,
                'notes_excerpt': ' '.join(x for x in [cn, bn, n] if x)[:200]
            })
    return out


def write_off_via_charges(cur, items, reason):
    # Create negative charter_charges rows if table exists
    cols = get_columns(cur, 'charter_charges')
    required = {'charter_id', 'amount'}
    if not required.issubset(set(cols.keys())):
        raise RuntimeError('charter_charges table not available with required columns (charter_id, amount)')

    inserted = 0
    for it in items:
        cid = it['charter_id']
        amt = -abs(float(it['balance']))
        desc_col = 'description' if 'description' in cols else None
        cat_col = 'category' if 'category' in cols else None
        created_col = 'created_at' if 'created_at' in cols else None

        fields = ['charter_id', 'amount']
        values = [cid, amt]
        if desc_col:
            fields.append(desc_col); values.append(f'Write-off {YEAR} {reason}')
        if cat_col:
            fields.append(cat_col); values.append('write_off_bad_debt')
        if created_col:
            fields.append(created_col); values.append(dt.datetime.utcnow())

        placeholders = ','.join(['%s'] * len(values))
        cur.execute(
            f"INSERT INTO charter_charges ({','.join(fields)}) VALUES ({placeholders})",
            tuple(values)
        )
        inserted += cur.rowcount

        # Optionally set balance to zero if balance column exists
        ccols = get_columns(cur, 'charters')
        if 'balance' in ccols:
            cur.execute("UPDATE charters SET balance = 0 WHERE charter_id = %s", (cid,))

    return inserted


def fetch_missing_driver_suggestions(cur):
    ccols = get_columns(cur, 'charters')
    has_driver_name = 'driver_name' in ccols

    # Charters lacking assigned_driver_id
    cur.execute(
        """
        SELECT charter_id, reserve_number, charter_date, assigned_driver_id,
               COALESCE(driver_name, '') AS driver_name
        FROM charters
        WHERE charter_date >= %s AND charter_date <= %s
          AND (assigned_driver_id IS NULL OR assigned_driver_id = 0)
        ORDER BY charter_date
        """,
        (dt.date(YEAR, 1, 1), dt.date(YEAR, 12, 31))
    )
    rows = cur.fetchall()

    # Employee name map
    ecols = get_columns(cur, 'employees')
    name_col = 'full_name' if 'full_name' in ecols else ('employee_name' if 'employee_name' in ecols else None)
    emp_map = {}
    if name_col:
        cur.execute(f"SELECT employee_id, {name_col} FROM employees")
        emp_map = {n.lower(): eid for eid, n in cur.fetchall() if n}

    suggestions = []
    # Exact name match heuristic
    for charter_id, rn, cdate, did, dname in rows:
        suggestion = None
        if dname and dname.strip():
            key = dname.strip().lower()
            if key in emp_map:
                suggestion = emp_map[key]
        # Fallback: driver_payroll
        if suggestion is None:
            try:
                cur.execute(
                    """
                    SELECT dp.employee_id
                    FROM driver_payroll dp
                    WHERE (dp.charter_id = %s OR dp.reserve_number = %s)
                      AND dp.employee_id IS NOT NULL
                    LIMIT 1
                    """,
                    (charter_id, rn)
                )
                r = cur.fetchone()
                if r and r[0]:
                    suggestion = r[0]
            except Exception:
                pass

        suggestions.append({
            'charter_id': charter_id,
            'reserve_number': rn,
            'charter_date': cdate,
            'driver_name': dname,
            'suggested_employee_id': suggestion,
        })

    return suggestions


def apply_driver_updates(cur, suggestions):
    applied = 0
    for s in suggestions:
        emp_id = s['suggested_employee_id']
        if emp_id:
            cur.execute(
                "UPDATE charters SET assigned_driver_id = %s WHERE charter_id = %s",
                (emp_id, s['charter_id'])
            )
            applied += cur.rowcount
    return applied


def write_csv(path, rows, fieldnames):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def fetch_client_names(cur):
    cols = get_columns(cur, 'clients')
    name_col = 'client_name' if 'client_name' in cols else None
    if not name_col:
        return {}
    cur.execute(f"SELECT client_id, {name_col} FROM clients")
    return {cid: name for cid, name in cur.fetchall()}


def payment_summary_for(cur, charter_id, reserve_number):
    pcols = get_columns(cur, 'payments')
    amt_expr = 'COALESCE(amount, payment_amount)'
    method_col = 'payment_method' if 'payment_method' in pcols else (
        'qb_payment_type' if 'qb_payment_type' in pcols else None
    )
    notes_col = 'notes' if 'notes' in pcols else None

    select_bits = [
        f'ROUND(SUM({amt_expr}), 2) AS total_paid',
        'COUNT(*) AS payment_count',
        'MAX(payment_date) AS last_payment_date'
    ]
    if method_col:
        select_bits.append(f"STRING_AGG(DISTINCT COALESCE({method_col}::text,''), '|') AS methods")
    if notes_col:
        select_bits.append(f"MAX({notes_col}) AS any_note")

    cur.execute(
        f"""
        SELECT {', '.join(select_bits)}
        FROM payments
        WHERE (charter_id = %s OR (%s IS NULL AND reserve_number = %s))
        """,
        (charter_id, charter_id, reserve_number)
    )
    rec = cur.fetchone()
    if not rec:
        return {'payment_total': None, 'payment_count': 0, 'last_payment_date': None, 'payment_methods': None}
    # Map by position respecting dynamic columns
    idx = 0
    total_paid = rec[idx]; idx += 1
    count = rec[idx]; idx += 1
    last_dt = rec[idx]; idx += 1
    methods = None
    if method_col:
        methods = rec[idx]; idx += 1
    # any_note is not output to keep CSV concise
    return {
        'payment_total': float(total_paid) if total_paid is not None else None,
        'payment_count': int(count or 0),
        'last_payment_date': last_dt,
        'payment_methods': methods,
    }


def main():
    parser = argparse.ArgumentParser(description='Analyze and remediate 2012 charters: penny-marked, cancelled-with-balance, uncollectible, missing drivers.')
    parser.add_argument('--write', action='store_true', help='Apply changes (otherwise dry-run).')
    parser.add_argument('--apply-classification', action='store_true', help='Apply inferred classification to charter_data JSON.')
    parser.add_argument('--remove-penny-payments', action='store_true', help='Delete $0.01 payment rows for classified free charters (requires override-key).')
    parser.add_argument('--override-key', type=str, default=None, help='Override key for protected deletion in payments.')
    parser.add_argument('--write-off', action='store_true', help='Insert negative charter_charges to write off uncollectible balances and zero balance.')
    parser.add_argument('--driver-apply', action='store_true', help='Apply high-confidence driver assignment updates.')
    parser.add_argument('--min-days-overdue', type=int, default=120, help='Threshold for uncollectible candidates.')

    args = parser.parse_args()

    reports = ensure_reports_dir()
    conn = None
    try:
        conn = db_connect()
        cur = conn.cursor()

        client_names = fetch_client_names(cur)

        # 1) Penny-marked
        penny_rows = fetch_penny_marked(cur)
        # Enrich with client name and payment summary
        for r in penny_rows:
            r['client_name'] = client_names.get(r.get('client_id'))
            ps = payment_summary_for(cur, r.get('charter_id'), r.get('reserve_number'))
            r.update(ps)
        penny_csv = os.path.join(reports, f'2012_penny_marked_candidates.csv')
        write_csv(
            penny_csv,
            penny_rows,
            ['charter_id','reserve_number','charter_date','client_id','client_name','booking_status','status','notes_excerpt','proposed_classification','payment_total','payment_count','last_payment_date','payment_methods','payment_ids']
        )
        print(f"Wrote: {penny_csv}")

        # 2) Cancelled with balance
        cancelled_rows = fetch_cancelled_with_balance(cur)
        for r in cancelled_rows:
            r['client_name'] = client_names.get(r.get('client_id'))
            ps = payment_summary_for(cur, r.get('charter_id'), r.get('reserve_number'))
            r.update(ps)
        cancelled_csv = os.path.join(reports, f'2012_cancelled_with_balance.csv')
        write_csv(cancelled_csv, cancelled_rows, ['charter_id','reserve_number','charter_date','client_id','client_name','balance','payment_total','payment_count','last_payment_date','notes_excerpt'])
        print(f"Wrote: {cancelled_csv}")

        # 3) Uncollectible candidates
        uncollectible = fetch_uncollectible_candidates(cur, min_days_overdue=args.min_days_overdue)
        for r in uncollectible:
            r['client_name'] = client_names.get(r.get('client_id'))
            ps = payment_summary_for(cur, r.get('charter_id'), r.get('reserve_number'))
            r.update(ps)
        uncollectible_csv = os.path.join(reports, f'2012_uncollectible_candidates.csv')
        write_csv(uncollectible_csv, uncollectible, ['charter_id','reserve_number','charter_date','age_days','balance','client_id','client_name','payment_total','payment_count','last_payment_date','notes_excerpt'])
        print(f"Wrote: {uncollectible_csv}")

        # 4) Missing driver suggestions
        driver_suggestions = fetch_missing_driver_suggestions(cur)
        # Attach client names for context
        # Fetch client_id for these charters
        if driver_suggestions:
            ids = tuple([s['charter_id'] for s in driver_suggestions])
            try:
                if ids:
                    cur.execute(
                        f"SELECT charter_id, client_id FROM charters WHERE charter_id IN ({','.join(['%s']*len(ids))})",
                        ids
                    )
                    cid_map = {cid: clid for cid, clid in cur.fetchall()}
                    for s in driver_suggestions:
                        clid = cid_map.get(s['charter_id'])
                        s['client_id'] = clid
                        s['client_name'] = client_names.get(clid)
            except Exception:
                pass
        drivers_csv = os.path.join(reports, f'2012_missing_driver_suggestions.csv')
        write_csv(drivers_csv, driver_suggestions, ['charter_id','reserve_number','charter_date','client_id','client_name','driver_name','suggested_employee_id'])
        print(f"Wrote: {drivers_csv}")

        if args.write:
            total_updated = total_deleted = total_inserted = total_driver = 0

            if args.apply_classification or args.remove_penny_payments:
                if args.remove_penny_payments and not args.override_key:
                    raise RuntimeError('Deleting from payments requires --override-key (ALLOW_DELETE_PAYMENTS_YYYYMMDD)')
                upd, dele = apply_classification_and_remove_pennies(
                    cur, penny_rows, args.override_key,
                    apply_classification=args.apply_classification,
                    remove_payments=args.remove_penny_payments,
                )
                total_updated += upd
                total_deleted += dele

            if args.write_off and uncollectible:
                ins = write_off_via_charges(cur, uncollectible, reason='uncollectible')
                total_inserted += ins

            if args.driver_apply and driver_suggestions:
                applied = apply_driver_updates(cur, [s for s in driver_suggestions if s['suggested_employee_id']])
                total_driver += applied

            conn.commit()
            print(f"APPLY summary: JSON updated={total_updated}, payments deleted={total_deleted}, writeoff rows inserted={total_inserted}, drivers set={total_driver}")
        else:
            print("Dry-run only: no DB changes applied. Use --write with flags to apply.")

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            if conn:
                conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
