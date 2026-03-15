"""
Backfill missing data from LMS (Access) into PostgreSQL WITHOUT duplication.

Principles:
- Use reserve_number as the business key for all joins (not charter_id).
- Insert only if missing (NOT EXISTS checks); dry-run by default.
- After payment inserts, recalc charters.paid_amount and balance by reserve_number.

Requirements:
- Windows with Access ODBC driver.
- Env: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

Usage:
  python -X utf8 scripts/backfill_from_lms.py              # dry run
  python -X utf8 scripts/backfill_from_lms.py --write      # apply changes
  python -X utf8 scripts/backfill_from_lms.py --limit 200  # limit scanning
"""
import os
import sys
import argparse
import datetime as dt
import psycopg2

try:
    import pyodbc
except Exception as e:
    pyodbc = None


def get_pg_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        dbname=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***'),
    )


def get_lms_conn(lms_path: str):
    if pyodbc is None:
        raise RuntimeError("pyodbc not available; install Access ODBC driver + pyodbc")
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};"
    return pyodbc.connect(conn_str)


def get_pg_columns(cur, table: str):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def table_exists(cur, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        )
        """,
        (table,)
    )
    return cur.fetchone()[0]


def scan_lms(lms_cur, limit=None):
    # Reserve (charters)
    reserve_cols = [c[0] for c in lms_cur.execute("SELECT TOP 1 * FROM Reserve").description]
    has_est_charge = 'Est_Charge' in reserve_cols or 'EstCharge' in reserve_cols
    est_col = 'Est_Charge' if 'Est_Charge' in reserve_cols else ('EstCharge' if 'EstCharge' in reserve_cols else None)

    # Access rejects aliasing a column to the same name; only add AS when column differs
    if est_col and est_col.lower() != 'est_charge':
        est_expr = f", {est_col} AS Est_Charge"
    elif est_col:
        est_expr = f", {est_col}"
    else:
        est_expr = ", Rate AS Est_Charge"

    sql_res = "SELECT Reserve_No, Account_No, PU_Date" + est_expr + " FROM Reserve ORDER BY PU_Date"
    if limit:
        # Access SQL uses TOP, so recompose
        sql_res = sql_res.replace("SELECT ", f"SELECT TOP {int(limit)} ")
    lms_reserves = []
    for r in lms_cur.execute(sql_res):
        lms_reserves.append({
            'reserve_number': str(r.Reserve_No).zfill(6) if r.Reserve_No is not None else None,
            'account_number': getattr(r, 'Account_No', None),
            'charter_date': getattr(r, 'PU_Date', None),
            'est_charge': getattr(r, 'Est_Charge', None),
        })

    # Payments
    pay_cols = [c[0] for c in lms_cur.execute("SELECT TOP 1 * FROM Payment").description]
    date_col = 'LastUpdated' if 'LastUpdated' in pay_cols else ('PaymentDate' if 'PaymentDate' in pay_cols else None)
    sql_pay = "SELECT PaymentID, Account_No, Reserve_No, Amount, [Key] AS payment_key" + (f", {date_col} AS payment_date" if date_col else ", LastUpdated AS payment_date") + " FROM Payment ORDER BY PaymentID"
    if limit:
        sql_pay = sql_pay.replace("SELECT ", f"SELECT TOP {int(limit)} ")
    lms_payments = []
    for p in lms_cur.execute(sql_pay):
        lms_payments.append({
            'payment_id': getattr(p, 'PaymentID', None),
            'account_number': getattr(p, 'Account_No', None),
            'reserve_number': str(p.Reserve_No).zfill(6) if getattr(p, 'Reserve_No', None) is not None else None,
            'amount': float(getattr(p, 'Amount', 0) or 0),
            'payment_key': getattr(p, 'payment_key', None),
            'payment_date': getattr(p, 'payment_date', None),
        })

    return lms_reserves, lms_payments


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply inserts')
    ap.add_argument('--limit', type=int, default=None, help='Limit LMS rows scanned (for testing)')
    ap.add_argument('--lms-path', default=r'L:\\limo\\lms.mdb', help='Path to LMS Access DB')
    args = ap.parse_args()

    pg = get_pg_conn()
    pg_cur = pg.cursor()

    # Introspect PG schemas
    has_charters = table_exists(pg_cur, 'charters')
    has_payments = table_exists(pg_cur, 'payments')
    has_charges = table_exists(pg_cur, 'charter_charges')
    pay_cols = get_pg_columns(pg_cur, 'payments') if has_payments else []
    char_cols = get_pg_columns(pg_cur, 'charters') if has_charters else []
    charge_cols = get_pg_columns(pg_cur, 'charter_charges') if has_charges else []

    # Preload existing identifiers
    existing_reserve = set()
    if has_charters:
        pg_cur.execute("SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
        existing_reserve = {r[0] for r in pg_cur.fetchall()}

    # Create date picker for payments
    pay_date_col = None
    for c in ('payment_date', 'created_at', 'last_updated', 'updated_at'):
        if c in pay_cols:
            pay_date_col = c
            break

    # LMS
    try:
        lms = get_lms_conn(args.lms_path)
    except Exception as e:
        print(f"Cannot open LMS at {args.lms_path}: {e}", file=sys.stderr)
        pg.close()
        sys.exit(2)
    lms_cur = lms.cursor()
    lms_res, lms_pays = scan_lms(lms_cur, args.limit)

    # Determine missing charters by reserve_number
    to_insert_charters = []
    if has_charters:
        for row in lms_res:
            rn = row['reserve_number']
            if not rn:
                continue
            if rn not in existing_reserve:
                to_insert_charters.append(row)

    # Determine missing payments via (reserve_number, amount, date)
    to_insert_payments = []
    if has_payments:
        for p in lms_pays:
            rn = p['reserve_number']
            amt = p['amount']
            dt_val = p['payment_date']
            if not rn or amt is None or dt_val is None:
                continue
            # Normalize date-only for comparison
            if isinstance(dt_val, dt.datetime):
                d_only = dt_val.date()
            elif isinstance(dt_val, dt.date):
                d_only = dt_val
            else:
                # Attempt parse
                try:
                    d_only = dt.datetime.fromisoformat(str(dt_val)).date()
                except Exception:
                    continue
            # NOT EXISTS check in PG
            if pay_date_col:
                pg_cur.execute(
                    f"""
                    SELECT 1 FROM payments
                    WHERE reserve_number = %s
                      AND (CASE WHEN %s = 'amount' THEN amount ELSE COALESCE(amount, payment_amount) END) = %s
                      AND CAST({pay_date_col} AS DATE) = %s
                    LIMIT 1
                    """,
                    (rn, 'amount', amt, d_only)
                )
            else:
                pg_cur.execute("SELECT 1 WHERE false")
            exists = pg_cur.fetchone()
            if not exists:
                to_insert_payments.append({**p, 'date_only': d_only})

    print("\nBackfill plan (dry-run by default):")
    print(f"  Missing charters to insert: {len(to_insert_charters)}")
    print(f"  Missing payments to insert: {len(to_insert_payments)}")

    if not args.write:
        lms.close(); pg.close()
        return

    # Apply inserts
    inserted_charters = 0
    inserted_charges = 0
    if has_charters and to_insert_charters:
        # Build minimal insert set dynamically
        can_cols = set(char_cols)
        insert_cols = [c for c in (
            'reserve_number', 'account_number', 'charter_date', 'total_amount_due', 'paid_amount', 'balance', 'created_at'
        ) if c in can_cols]
        now = dt.datetime.now()
        for r in to_insert_charters:
            total = r['est_charge'] if r['est_charge'] is not None else 0
            values = {
                'reserve_number': r['reserve_number'],
                'account_number': r['account_number'],
                'charter_date': r['charter_date'],
                'total_amount_due': total,
                'paid_amount': 0,
                'balance': total,
                'created_at': now,
            }
            cols = [c for c in insert_cols if c in values]
            placeholders = ", ".join(["%s"] * len(cols))
            pg_cur.execute(
                f"INSERT INTO charters ({', '.join(cols)}) VALUES ({placeholders})",
                [values[c] for c in cols]
            )
            inserted_charters += 1
            # Also create a single charter_charge if table exists
            if has_charges:
                cc_cols_can = set(charge_cols)
                cc_cols = [c for c in (
                    'reserve_number', 'charter_id', 'description', 'amount', 'created_at'
                ) if c in cc_cols_can]
                # We don't have charter_id easily; rely on reserve_number if supported
                desc = 'Charter total (from LMS Est_Charge)'
                vals = {
                    'reserve_number': r['reserve_number'],
                    'description': desc,
                    'amount': total,
                    'created_at': now,
                }
                cols_cc = [c for c in cc_cols if c in vals]
                if cols_cc:
                    pg_cur.execute(
                        f"INSERT INTO charter_charges ({', '.join(cols_cc)}) VALUES ({', '.join(['%s']*len(cols_cc))})",
                        [vals[c] for c in cols_cc]
                    )
                    inserted_charges += 1

    inserted_payments = 0
    if has_payments and to_insert_payments:
        # Determine amount column
        amount_col = 'amount' if 'amount' in pay_cols else ('payment_amount' if 'payment_amount' in pay_cols else None)
        # Build dynamic column list
        insert_cols = [c for c in (
            'reserve_number', 'account_number', amount_col, 'payment_date', 'payment_key', 'created_at'
        ) if c and c in pay_cols]
        now = dt.datetime.now()
        for p in to_insert_payments:
            vals = {
                'reserve_number': p['reserve_number'],
                'account_number': p['account_number'],
                amount_col: p['amount'],
                'payment_date': p['date_only'],
                'payment_key': p['payment_key'],
                'created_at': now,
            }
            cols = [c for c in insert_cols if c in vals]
            if not cols:
                continue
            pg_cur.execute(
                f"INSERT INTO payments ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))})",
                [vals[c] for c in cols]
            )
            inserted_payments += 1

    # Recalculate charter.paid_amount and balance via reserve_number
    if inserted_payments > 0 and has_charters and has_payments:
        pg_cur.execute(
            """
            WITH payment_sums AS (
                SELECT 
                    reserve_number,
                    ROUND(SUM(COALESCE(amount, payment_amount, 0))::numeric, 2) as actual_paid
                FROM payments
                WHERE reserve_number IS NOT NULL
                GROUP BY reserve_number
            )
            UPDATE charters c
            SET paid_amount = ps.actual_paid,
                balance = c.total_amount_due - ps.actual_paid
            FROM payment_sums ps
            WHERE c.reserve_number = ps.reserve_number
            """
        )

    pg.commit()
    print("\nApplied:")
    print(f"  Inserted charters: {inserted_charters}")
    if has_charges:
        print(f"  Inserted charter_charges: {inserted_charges}")
    print(f"  Inserted payments: {inserted_payments}")

    lms.close(); pg.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"Backfill failed: {e}", file=sys.stderr)
        sys.exit(2)
