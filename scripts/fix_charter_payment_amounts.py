#!/usr/bin/env python
"""
Normalize charter_payments.amount to the actual payment amount for safe cases.
SAFE case criteria:
  - payments.reserve_number = charter_payments.charter_id (explicit per-charter payment)
  - Given payment_id appears exactly once in charter_payments (no split across charters)
  - Absolute difference > $0.01

Usage:
  python -X utf8 scripts/fix_charter_payment_amounts.py            # dry run summary
  python -X utf8 scripts/fix_charter_payment_amounts.py --charter 017720  # dry run for one charter
  python -X utf8 scripts/fix_charter_payment_amounts.py --write --charter 017720  # apply for one
  python -X utf8 scripts/fix_charter_payment_amounts.py --write     # apply all safe corrections

This script also recomputes charters.paid_amount and balance for affected charters
based on charter_charges sum(total) and summed charter_payments amounts.
"""
import argparse
import psycopg2
from decimal import Decimal


def get_conn():
    return psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REDACTED***')

def create_backup(cur, table_name='charter_payments'):
    import datetime
    bname = f"{table_name}_BACKUP_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cur.execute(f"CREATE TABLE {bname} AS TABLE {table_name}")
    return bname


def gather_candidates(cur, only_charter=None):
    params = []
    charter_filter = ""
    if only_charter:
        charter_filter = " AND cp.charter_id = %s"
        params.append(only_charter)

    cur.execute(f"""
        WITH cp_counts AS (
          SELECT payment_id, COUNT(*) AS cnt
          FROM charter_payments
          GROUP BY payment_id
        )
        SELECT 
            cp.id, cp.charter_id, cp.payment_id, cp.amount AS cp_amount,
            COALESCE(p.payment_amount, p.amount) AS pay_amount,
            p.payment_date, p.payment_method, p.payment_key
        FROM charter_payments cp
        JOIN payments p ON p.payment_id = cp.payment_id
        JOIN cp_counts c ON c.payment_id = cp.payment_id
        WHERE p.reserve_number = cp.charter_id
          AND c.cnt = 1
          AND ABS(COALESCE(p.payment_amount, p.amount) - cp.amount) > 0.01
          {charter_filter}
        ORDER BY cp.charter_id, p.payment_date, cp.id
    """, params)
    return cur.fetchall()


def recompute_charter(cur, reserve_number):
    # paid_amount from charter_payments
    cur.execute("SELECT COALESCE(SUM(amount),0) FROM charter_payments WHERE charter_id=%s", (reserve_number,))
    paid = cur.fetchone()[0]

    # total_amount_due: prefer charters.total_amount_due if set; otherwise sum charter_charges
    cur.execute("SELECT total_amount_due FROM charters WHERE reserve_number=%s", (reserve_number,))
    row = cur.fetchone()
    if row is None:
        # Charter id present in charter_payments but no matching charter record
        print(f"WARNING: charter {reserve_number} not found in charters table; skipping recompute.")
        return
    tad = row[0]
    if tad is None or float(tad) <= 0:
        cur.execute("SELECT COALESCE(SUM(amount),0) FROM charter_charges WHERE reserve_number=%s", (reserve_number,))
        tad = cur.fetchone()[0]

    # balance = total_amount_due - paid_amount
    balance = Decimal(tad or 0) - Decimal(paid or 0)

    cur.execute("""
        UPDATE charters
        SET paid_amount = %s,
            balance = %s
        WHERE reserve_number = %s
    """, (paid, balance, reserve_number))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply fixes')
    ap.add_argument('--charter', help='Limit to single reserve_number')
    ap.add_argument('--summary-only', action='store_true', help='Print summary per charter without listing every row')
    ap.add_argument('--max-rows', type=int, default=200, help='When not summary-only, limit row printout')
    args = ap.parse_args()

    conn = get_conn(); cur = conn.cursor()

    rows = gather_candidates(cur, args.charter)
    if not rows:
        print('No mismatched charter_payment amounts found for the given filter.')
        return

    total_delta = Decimal('0')
    affected_charters = set()
    print('='*100)
    print('Proposed corrections (cp.amount -> pay_amount)')
    print('='*100)
    if args.summary_only:
        # summarize per charter
        per_charter = {}
        for cp_id, charter_id, payment_id, cp_amt, pay_amt, dt, method, key in rows:
            delta = Decimal(pay_amt) - Decimal(cp_amt)
            total_delta += delta
            affected_charters.add(charter_id)
            agg = per_charter.setdefault(charter_id, {'rows':0,'delta':Decimal('0')})
            agg['rows'] += 1
            agg['delta'] += delta
        # print top by absolute delta
        top = sorted(per_charter.items(), key=lambda kv: abs(kv[1]['delta']), reverse=True)
        print('Top affected charters by absolute delta:')
        for charter_id, info in top[:50]:
            print(f"  charter={charter_id} rows={info['rows']} net_delta={info['delta']:+}")
    else:
        count = 0
        for cp_id, charter_id, payment_id, cp_amt, pay_amt, dt, method, key in rows:
            delta = Decimal(pay_amt) - Decimal(cp_amt)
            total_delta += delta
            affected_charters.add(charter_id)
            if count < args.max_rows:
                print(f"  cp_id={cp_id} charter={charter_id} payment_id={payment_id} date={dt} method={method} key={key} \n    cp_amount={cp_amt} -> pay_amount={pay_amt} (delta {delta:+})")
            count += 1
        if count > args.max_rows:
            print(f"  ... truncated {count - args.max_rows} more rows")

    print('\nSummary:')
    print(f"  Rows to correct: {len(rows)}")
    print(f"  Charters affected: {len(affected_charters)} -> {sorted(list(affected_charters))[:10]}{'...' if len(affected_charters)>10 else ''}")
    print(f"  Net decrease in paid_amount (sum of deltas): {total_delta}")

    if args.write:
        # backup before applying
        backup_name = create_backup(cur, 'charter_payments')
        print(f"Backup created: {backup_name}")
        for cp_id, charter_id, payment_id, cp_amt, pay_amt, dt, method, key in rows:
            cur.execute("UPDATE charter_payments SET amount = %s WHERE id = %s", (pay_amt, cp_id))
        for ch in affected_charters:
            try:
                recompute_charter(cur, ch)
            except Exception as e:
                print(f"ERROR recomputing charter {ch}: {e}")
        conn.commit()
        print(f"\nAPPLIED: Updated {len(rows)} charter_payments rows and recomputed {len(affected_charters)} charters.")
    else:
        print('\nDRY RUN ONLY (use --write to apply).')

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
