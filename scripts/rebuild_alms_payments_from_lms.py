import os
import csv
import argparse
from datetime import datetime
from collections import defaultdict

import psycopg2

try:
    import pyodbc
except ImportError:
    pyodbc = None

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def read_overrides(path):
    overrides = []
    if not path or not os.path.exists(path):
        return overrides
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            o = {
                "reference_number": (row.get("reference_number") or "").strip(),
                "payment_id": (row.get("payment_id") or "").strip(),
                "reserve_number": (row.get("reserve_number") or "").strip(),
                "allocated_amount": row.get("allocated_amount"),
                "classification": (row.get("classification") or "").strip().lower(),
                "notes": (row.get("notes") or "").strip(),
            }
            if o["allocated_amount"] not in (None, ""):
                try:
                    o["allocated_amount"] = float(o["allocated_amount"]) 
                except Exception:
                    o["allocated_amount"] = None
            overrides.append(o)
    return overrides


def fetch_lms_payments(mdb_path):
    if pyodbc is None:
        raise RuntimeError("pyodbc is required to read LMS .mdb; please install it.")
    conn = pyodbc.connect(rf'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={mdb_path};')
    cur = conn.cursor()
    # Attempt to read optional PaymentDate if present
    # Known LMS Payment columns: Account_No, Amount, Key, Reserve_No, LastUpdated, LastUpdatedBy, PaymentID
    cur.execute("SELECT PaymentID, Reserve_No, Amount, LastUpdated, Key, Account_No FROM Payment ORDER BY PaymentID")
    rows = []
    for r in cur.fetchall():
        payment_id = str(r[0]).strip() if r[0] is not None else ""
        reserve = str(r[1]).strip() if r[1] is not None else ""
        amount = float(r[2] or 0)
        payment_date = r[3] if len(r) > 3 else None
        payment_key = str(r[4]).strip() if len(r) > 4 and r[4] is not None else ""
        account_no = str(r[5]).strip() if len(r) > 5 and r[5] is not None else ""
        rows.append({
            "payment_id": payment_id,
            "reserve_number": reserve,
            "amount": amount,
            "payment_date": payment_date,
            "payment_key": payment_key,
            "account_number": account_no,
        })
    cur.close()
    conn.close()
    return rows


def build_rows(lms_rows, overrides, include_liabilities=True):
    by_key = defaultdict(list)
    for o in overrides:
        key = (o.get("payment_id") or "", o.get("reference_number") or "")
        by_key[key].append(o)

    out = []
    summary = {
        "total_lms": len(lms_rows),
        "total_amount": sum(r["amount"] for r in lms_rows),
        "overrides": len(overrides),
        "rows": 0,
        "liabilities": 0,
        "manual_repairs": 0,
        "splits": 0,
    }

    for r in lms_rows:
        pid = r["payment_id"]
        default_ref = f"LMS-Payment-{pid}" if pid else "LMS-Payment"
        # Collect all overrides by payment_id
        o_hits = []
        for (opid, ref), vals in by_key.items():
            if opid == pid:
                o_hits.extend([(ref, v) for v in vals])

        if o_hits:
            grouped = defaultdict(list)
            for ref, v in o_hits:
                grouped[ref].append(v)
            summary["splits"] += len(grouped)
            for ref_num, rows in grouped.items():
                for v in rows:
                    cls = v.get("classification") or ""
                    reserve_number = v.get("reserve_number") or ""
                    amt = v.get("allocated_amount") if v.get("allocated_amount") is not None else r["amount"]
                    notes = v.get("notes") or ""
                    if cls == "deposit_liability":
                        if not include_liabilities:
                            continue
                        summary["liabilities"] += 1
                        out.append({
                            "reserve_number": None,
                            "amount": amt,
                            "payment_method": "unknown",
                            "reference_number": ref_num or default_ref,
                            "payment_date": r.get("payment_date"),
                            "payment_key": r.get("payment_key"),
                            "account_number": r.get("account_number"),
                            "notes": notes or "Unused non-refundable deposit",
                            "classification": cls,
                        })
                    else:
                        if cls == "manual_repair":
                            summary["manual_repairs"] += 1
                        method = "trade_of_services" if cls == "trade_of_services" else "unknown"
                        out.append({
                            "reserve_number": reserve_number or r["reserve_number"],
                            "amount": amt,
                            "payment_method": method,
                            "reference_number": ref_num or default_ref,
                            "payment_date": r.get("payment_date"),
                            "payment_key": r.get("payment_key"),
                            "account_number": r.get("account_number"),
                            "notes": notes,
                            "classification": cls,
                        })
        else:
            out.append({
                "reserve_number": r["reserve_number"],
                "amount": r["amount"],
                "payment_method": "unknown",
                "reference_number": default_ref,
                "payment_date": r.get("payment_date"),
                "payment_key": r.get("payment_key"),
                "account_number": r.get("account_number"),
                "notes": "",
                "classification": "",
            })

    summary["rows"] = len(out)
    return out, summary


def backup_table(cur):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"payments_backup_{ts}"
    cur.execute(f"CREATE TABLE IF NOT EXISTS {backup_name} AS SELECT * FROM payments")
    return backup_name


def apply_import(rows, dry_run=True):
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    try:
        if not dry_run:
            backup = backup_table(cur)
            print(f"Backup table created: {backup}")
            # Rebuild: start fresh
            cur.execute("TRUNCATE TABLE payments RESTART IDENTITY CASCADE")

        insert_sql = (
            "INSERT INTO payments (reserve_number, amount, payment_method, reference_number, payment_date, notes, status, is_deposited, payment_key, account_number) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        )
        inserted = 0
        for r in rows:
            params = (
                r.get("reserve_number"),
                r.get("amount"),
                r.get("payment_method"),
                r.get("reference_number"),
                r.get("payment_date"),
                r.get("notes"),
                'pending',
                False,
                r.get("payment_key"),
                r.get("account_number"),
            )
            if dry_run:
                inserted += 1
            else:
                cur.execute(insert_sql, params)
                inserted += 1

        if dry_run:
            print(f"Dry-run: would insert {inserted} rows into payments.")
        else:
            conn.commit()
            print(f"Inserted {inserted} rows into payments. Commit complete.")
    except Exception as e:
        if not dry_run:
            conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Rebuild ALMS payments from LMS with overrides")
    parser.add_argument("--lms-mdb", default=r"L:\\limo\\backups\\lms.mdb")
    parser.add_argument("--overrides", default=r"L:\\limo\\data\\payment_overrides.csv")
    parser.add_argument("--write", action="store_true", help="Apply changes to the database")
    parser.add_argument("--exclude-liabilities", action="store_true", help="Exclude deposit_liability rows")
    args = parser.parse_args()

    overrides = read_overrides(args.overrides)
    lms_rows = fetch_lms_payments(args.lms_mdb)
    rows, summary = build_rows(lms_rows, overrides, include_liabilities=not args.exclude_liabilities)
    print("Build summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    apply_import(rows, dry_run=not args.write)


if __name__ == "__main__":
    main()
