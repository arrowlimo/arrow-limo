import os
import sys
import argparse
import hashlib
from datetime import datetime

import pyodbc
import psycopg2
import psycopg2.extras


def connect_lms(lms_path: str):
    conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={lms_path};"
    return pyodbc.connect(conn_str)


def connect_pg():
    host = os.getenv('DB_HOST', 'localhost')
    name = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def normalize_name(name: str):
    if not name:
        return None
    n = name.strip()
    n = ' '.join(n.split())
    return n


def backup_table(cur, table_name: str):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{table_name}_backup_{ts}"
    cur.execute(f"CREATE TABLE {backup_name} AS SELECT * FROM {table_name}")
    return backup_name


def sync_clients(lms_cur, pg_cur, apply: bool, limit: int | None):
    # Load existing clients for quick lookup (include account_number if present)
    pg_cur.execute("SELECT client_id, COALESCE(LOWER(TRIM(client_name)), ''), COALESCE(LOWER(TRIM(email)), ''), COALESCE(TRIM(account_number::text), '') FROM clients")
    rows = pg_cur.fetchall()
    def norm_acct(a):
        a = (a or '').strip()
        return a.lower()
    existing_triplet = {(r[1], r[2], norm_acct(r[3])): r[0] for r in rows}
    existing_accounts = { norm_acct(r[3]) for r in rows if norm_acct(r[3]) }

    # Pull candidate client info from LMS Reserve
    lms_cur.execute("SELECT DISTINCT Name, EMail, Account_No FROM Reserve WHERE Name IS NOT NULL")
    rows = lms_cur.fetchall()
    to_insert = []
    for name, email, account_no in rows[:limit] if limit else rows:
        cname = normalize_name(name)
        if not cname:
            continue
        email_norm = (email or '').strip().lower()
        acct_norm = (str(account_no).strip().lower() if account_no is not None else '')
        # Skip rows without an account_number (clients.account_number is NOT NULL)
        if not acct_norm:
            continue
        # If account_number exists in clients, skip to respect unique constraint
        if acct_norm in existing_accounts:
            continue
        key = (cname.lower(), email_norm, acct_norm)
        if key not in existing_triplet:
            to_insert.append((cname, email_norm if email_norm else None, account_no))

    print(f"[clients] missing from Postgres: {len(to_insert)}")
    if not apply:
        return 0

    if to_insert:
        backup_table(pg_cur, 'clients')
        psycopg2.extras.execute_values(
            pg_cur,
            "INSERT INTO clients (client_name, email, account_number) VALUES %s",
            to_insert
        )
    return len(to_insert)


def sync_charters(lms_cur, pg_cur, apply: bool, limit: int | None):
    # Existing reserve_numbers
    pg_cur.execute("SELECT reserve_number FROM charters WHERE reserve_number IS NOT NULL")
    existing_res = {r[0] for r in pg_cur.fetchall()}

    lms_cur.execute("""
        SELECT Reserve_No, Account_No, PU_Date, Rate, Balance, Name
        FROM Reserve
        WHERE Reserve_No IS NOT NULL
        ORDER BY Reserve_No
    """)
    rows = lms_cur.fetchall()
    to_insert = []
    for reserve_no, account_no, pu_date, rate, balance, name in rows[:limit] if limit else rows:
        rn = str(reserve_no).zfill(6) if isinstance(reserve_no, (int, float)) else str(reserve_no)
        if rn not in existing_res:
            to_insert.append((rn, account_no, pu_date, rate, balance, normalize_name(name)))

    print(f"[charters] missing from Postgres: {len(to_insert)}")
    if not apply:
        return 0

    if to_insert:
        backup_table(pg_cur, 'charters')
        psycopg2.extras.execute_values(
            pg_cur,
            """
            INSERT INTO charters (reserve_number, account_number, charter_date, rate, balance, driver_name)
            VALUES %s
            """,
            to_insert
        )
    return len(to_insert)


def sync_payments(lms_cur, pg_cur, apply: bool, limit: int | None):
    # Build a set of existing composite keys for payments
    pg_cur.execute("SELECT reserve_number, amount, payment_date FROM payments WHERE reserve_number IS NOT NULL")
    existing = {(str(r[0]), float(r[1]) if r[1] is not None else None, r[2]) for r in pg_cur.fetchall()}

    lms_cur.execute("SELECT Reserve_No, Amount, LastUpdated, Account_No FROM Payment WHERE Reserve_No IS NOT NULL")
    rows = lms_cur.fetchall()
    to_insert = []
    for reserve_no, amount, last_updated, account_no in rows[:limit] if limit else rows:
        rn = str(reserve_no).zfill(6) if isinstance(reserve_no, (int, float)) else str(reserve_no)
        amt = float(amount) if amount is not None else None
        dt = last_updated.date() if hasattr(last_updated, 'date') else last_updated
        key = (rn, amt, dt)
        if key not in existing and rn and amt is not None and dt is not None:
            to_insert.append((account_no, rn, amt, dt))

    print(f"[payments] missing from Postgres (composite reserve_number+amount+date): {len(to_insert)}")
    if not apply:
        return 0

    if to_insert:
        backup_table(pg_cur, 'payments')
        psycopg2.extras.execute_values(
            pg_cur,
            """
            INSERT INTO payments (account_number, reserve_number, amount, payment_date)
            VALUES %s
            """,
            to_insert
        )
    return len(to_insert)


def recalc_charter_balances(pg_cur, apply: bool):
    print("[balances] recalculating charter balances by reserve_number…")
    if not apply:
        return
    pg_cur.execute("""
        WITH payment_sums AS (
            SELECT reserve_number,
                   ROUND(SUM(COALESCE(amount, 0))::numeric, 2) AS actual_paid
            FROM payments
            WHERE reserve_number IS NOT NULL
            GROUP BY reserve_number
        )
        UPDATE charters c
        SET paid_amount = ps.actual_paid,
            balance = c.total_amount_due - ps.actual_paid
        FROM payment_sums ps
        WHERE c.reserve_number = ps.reserve_number
    """)


def main():
    ap = argparse.ArgumentParser(description="Sync missing LMS data into Postgres with duplicate safeguards")
    ap.add_argument('--lms-path', default=os.getenv('LMS_PATH', r'L:\limo\backups\lms.mdb'))
    ap.add_argument('--limit', type=int, default=None, help='Limit rows for testing')
    ap.add_argument('--write', action='store_true', help='Apply inserts (default: dry-run)')
    args = ap.parse_args()

    try:
        lms = connect_lms(args.lms_path)
        lcur = lms.cursor()
    except Exception as e:
        print(f"Failed to open LMS at {args.lms_path}: {e}")
        sys.exit(1)

    try:
        pg = connect_pg()
        pg.autocommit = False
        pcur = pg.cursor()
    except Exception as e:
        print(f"Failed to connect to Postgres: {e}")
        sys.exit(1)

    try:
        c_ins = sync_clients(lcur, pcur, args.write, args.limit)
        ch_ins = sync_charters(lcur, pcur, args.write, args.limit)
        p_ins = sync_payments(lcur, pcur, args.write, args.limit)
        recalc_charter_balances(pcur, args.write)

        if args.write:
            pg.commit()
            print(f"Apply complete. clients={c_ins}, charters={ch_ins}, payments={p_ins}")
        else:
            pg.rollback()
            print(f"Dry-run complete. Would insert: clients={c_ins}, charters={ch_ins}, payments={p_ins}")
    except Exception as e:
        pg.rollback()
        print(f"Sync failed: {e}")
        sys.exit(1)
    finally:
        try:
            lms.close()
        except:
            pass
        try:
            pg.close()
        except:
            pass


if __name__ == '__main__':
    main()
