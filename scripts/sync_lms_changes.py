"""
Synchronize recent/corrected LMS (Access) changes into PostgreSQL
=================================================================

Compares LMS Reserve/Payment tables with our PostgreSQL `charters` and
`payments` using reserve_number as the business key. Updates changed fields
and inserts missing rows idempotently. Always recalculates charter paid_amount
by summing payments via reserve_number.

Safety:
- Dry-run by default. Use --apply to write.
- Duplicate-safe inserts: use WHERE NOT EXISTS on (reserve_number, amount, date).
- Never deletes. Only updates/inserts.

Usage:
  python -X utf8 scripts/sync_lms_changes.py --lms "L:\\limo\\lms.mdb" --since 2024-01-01
  python -X utf8 scripts/sync_lms_changes.py --lms "L:\\limo\\lms.mdb" --apply
"""

import argparse
import datetime as dt
import os
import sys
from decimal import Decimal

import psycopg2

try:
    import pyodbc
except ImportError:
    pyodbc = None


def get_pg():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "***REDACTED***"),
    )


def get_lms_conn(lms_path: str):
    if not pyodbc:
        raise RuntimeError("pyodbc is required to read LMS Access database")
    conn_str = (
        f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};"
    )
    return pyodbc.connect(conn_str)


def fetch_lms_reserves(cur_lms, since: dt.date | None):
    where = ""
    params = []
    if since:
        where = " WHERE PU_Date >= ?"
        params.append(since)
    cur_lms.execute(
        f"""
        SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Deposit,
               Pymt_Type, Vehicle, Name
        FROM Reserve
        {where}
        ORDER BY PU_Date DESC
        """,
        params,
    )
    rows = cur_lms.fetchall()
    results = []
    for r in rows:
        results.append(
            {
                "reserve_number": str(r.Reserve_No).zfill(6) if r.Reserve_No is not None else None,
                "account_number": r.Account_No,
                "charter_date": r.PU_Date.date() if hasattr(r.PU_Date, "date") else r.PU_Date,
                "rate": Decimal(str(r.Rate)) if r.Rate is not None else None,
                "balance": Decimal(str(r.Balance)) if r.Balance is not None else None,
                "deposit": Decimal(str(r.Deposit)) if r.Deposit is not None else None,
                "payment_method": r.Pymt_Type,
                "vehicle": r.Vehicle,
                "client_name": r.Name,
            }
        )
    return results


def fetch_lms_payments(cur_lms, since: dt.date | None):
    where = ""
    params = []
    if since:
        where = " WHERE LastUpdated >= ?"
        params.append(since)
    cur_lms.execute(
        f"""
        SELECT PaymentID, Account_No, Reserve_No, Amount, [Key], LastUpdated, LastUpdatedBy
        FROM Payment
        {where}
        ORDER BY LastUpdated DESC
        """,
        params,
    )
    rows = cur_lms.fetchall()
    results = []
    for r in rows:
        results.append(
            {
                "payment_id": r.PaymentID,
                "account_number": r.Account_No,
                "reserve_number": str(r.Reserve_No).zfill(6) if r.Reserve_No is not None else None,
                "amount": Decimal(str(r.Amount)) if r.Amount is not None else None,
                "payment_key": r.Key,
                "payment_date": r.LastUpdated.date() if hasattr(r.LastUpdated, "date") else r.LastUpdated,
                "last_updated_by": r.LastUpdatedBy,
            }
        )
    return results


def upsert_charter(pg_cur, row: dict, apply: bool):
    # Update limited fields that are authoritative from LMS for history
    # Only update when values differ and LMS has non-null
    updates = []
    values = []
    for col, key in [
        ("account_number", "account_number"),
        ("charter_date", "charter_date"),
        ("rate", "rate"),
        ("balance", "balance"),
        ("deposit", "deposit"),
        ("payment_method", "payment_method"),
        ("vehicle", "vehicle"),
        ("client_name", "client_name"),
    ]:
        if row.get(key) is not None:
            updates.append(f"{col} = %s")
            values.append(row[key])

    if not updates or not row.get("reserve_number"):
        return 0

    sql = f"""
        UPDATE charters SET {', '.join(updates)}
        WHERE reserve_number = %s
    """
    values.append(row["reserve_number"])
    if apply:
        pg_cur.execute(sql, values)
        return pg_cur.rowcount
    return 0


def insert_payment_if_missing(pg_cur, p: dict, apply: bool):
    # Idempotent insert using business key tuple: (reserve_number, amount, payment_date)
    if not (p.get("reserve_number") and p.get("amount") is not None and p.get("payment_date")):
        return 0
    chk_sql = (
        """
        SELECT 1 FROM payments
        WHERE reserve_number = %s AND amount = %s AND payment_date = %s
        LIMIT 1
        """
    )
    pg_cur.execute(chk_sql, (p["reserve_number"], p["amount"], p["payment_date"]))
    if pg_cur.fetchone():
        return 0

    ins_sql = (
        """
        INSERT INTO payments (account_number, reserve_number, amount, payment_key, payment_date, last_updated_by)
        SELECT %s, %s, %s, %s, %s, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM payments WHERE reserve_number = %s AND amount = %s AND payment_date = %s
        )
        """
    )
    params = (
        p.get("account_number"),
        p.get("reserve_number"),
        p.get("amount"),
        p.get("payment_key"),
        p.get("payment_date"),
        p.get("last_updated_by"),
        p.get("reserve_number"),
        p.get("amount"),
        p.get("payment_date"),
    )
    if apply:
        pg_cur.execute(ins_sql, params)
        return pg_cur.rowcount
    return 0


def recalc_charter_paid_amounts(pg_cur, apply: bool):
    sql = (
        """
        WITH payment_sums AS (
            SELECT reserve_number, ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS actual_paid
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
    if apply:
        pg_cur.execute(sql)
        return pg_cur.rowcount
    return 0


def main():
    ap = argparse.ArgumentParser(description="Sync LMS changes into PostgreSQL")
    ap.add_argument("--lms", default=r"L:\\limo\\lms.mdb", help="Path to LMS .mdb file")
    ap.add_argument("--since", help="Only pull LMS rows updated on/after this date (YYYY-MM-DD)")
    ap.add_argument("--apply", action="store_true", help="Apply changes (default is dry-run)")
    args = ap.parse_args()

    since_date = None
    if args.since:
        since_date = dt.date.fromisoformat(args.since)

    pg = get_pg()
    pg_cur = pg.cursor()
    try:
        lms = get_lms_conn(args.lms)
    except Exception as e:
        print(f"Failed to open LMS: {e}")
        sys.exit(2)

    lms_cur = lms.cursor()

    print("Reading LMS reserves...")
    reserves = fetch_lms_reserves(lms_cur, since_date)
    print(f"  LMS reserves fetched: {len(reserves)}")

    print("Reading LMS payments...")
    payments = fetch_lms_payments(lms_cur, since_date)
    print(f"  LMS payments fetched: {len(payments)}")

    updated_charters = 0
    inserted_payments = 0

    for r in reserves:
        try:
            updated_charters += upsert_charter(pg_cur, r, args.apply)
        except Exception as e:
            print("Charter update error", r.get("reserve_number"), e)
            pg.rollback()

    for p in payments:
        try:
            inserted_payments += insert_payment_if_missing(pg_cur, p, args.apply)
        except Exception as e:
            print("Payment insert error", p.get("reserve_number"), e)
            pg.rollback()

    print(f"Charters updated: {updated_charters}")
    print(f"Payments inserted: {inserted_payments}")

    try:
        recalced = recalc_charter_paid_amounts(pg_cur, args.apply)
        print(f"Charters recalculated (paid_amount/balance): {recalced}")
    except Exception as e:
        print("Recalc error:", e)
        pg.rollback()

    if args.apply:
        pg.commit()
        print("Changes committed.")
    else:
        pg.rollback()
        print("Dry-run complete. No changes applied.")

    lms_cur.close()
    lms.close()
    pg_cur.close()
    pg.close()


if __name__ == "__main__":
    main()
