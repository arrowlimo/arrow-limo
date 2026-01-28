import os
import sys
import argparse
from datetime import date, datetime
from decimal import Decimal
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def conn_cur():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    return conn, conn.cursor()


def ensure_account(cur, canonical_vendor: str, display_name: str = None):
    cur.execute("""
        INSERT INTO vendor_accounts (canonical_vendor, display_name)
        VALUES (%s, %s)
        ON CONFLICT (canonical_vendor) DO UPDATE SET display_name = EXCLUDED.display_name
        RETURNING account_id
    """, (canonical_vendor, display_name))
    return cur.fetchone()[0]


def get_account_id(cur, canonical_vendor: str):
    cur.execute("SELECT account_id FROM vendor_accounts WHERE canonical_vendor=%s", (canonical_vendor,))
    row = cur.fetchone()
    return row[0] if row else None


def add_invoice(cur, account_id: int, entry_date: date, amount: Decimal, invoice_number: str = None, notes: str = None):
    cur.execute("""
        INSERT INTO vendor_account_ledger (account_id, entry_date, entry_type, amount, external_ref, notes)
        VALUES (%s, %s, 'INVOICE', %s, %s, %s)
        RETURNING ledger_id
    """, (account_id, entry_date, amount, invoice_number, notes))
    return cur.fetchone()[0]


def add_payment(cur, account_id: int, entry_date: date, amount: Decimal, external_ref: str = None, notes: str = None):
    # Payments decrease balance: store as negative if positive provided
    amt = amount
    if amt > 0:
        amt = -amt
    cur.execute("""
        INSERT INTO vendor_account_ledger (account_id, entry_date, entry_type, amount, external_ref, notes)
        VALUES (%s, %s, 'PAYMENT', %s, %s, %s)
        RETURNING ledger_id
    """, (account_id, entry_date, amt, external_ref, notes))
    return cur.fetchone()[0]


def list_accounts(cur):
    cur.execute("SELECT account_id, canonical_vendor, display_name FROM vendor_accounts ORDER BY canonical_vendor")
    return cur.fetchall()


def ledger_for_account(cur, account_id: int):
    cur.execute("""
        SELECT entry_date, entry_type, amount, external_ref, notes
        FROM vendor_account_ledger
        WHERE account_id=%s
        ORDER BY entry_date ASC, CASE WHEN entry_type='INVOICE' THEN 0 ELSE 1 END, ledger_id ASC
    """, (account_id,))
    rows = cur.fetchall()
    balance = Decimal("0.00")
    entries = []
    for d, t, a, ref, n in rows:
        balance += Decimal(a)
        entries.append((d, t, Decimal(a), ref, n, Decimal(balance)))
    return entries


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def parse_amount(s: str) -> Decimal:
    return Decimal(s)


def main():
    ap = argparse.ArgumentParser(description="Vendor Accounts CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_addacc = sub.add_parser("add-account", help="Add or update a vendor account")
    sp_addacc.add_argument("canonical_vendor", help="Canonical vendor name (UPPERCASE)")
    sp_addacc.add_argument("--display-name", default=None)

    sp_addinv = sub.add_parser("add-invoice", help="Add unpaid invoice to a vendor account")
    sp_addinv.add_argument("canonical_vendor")
    sp_addinv.add_argument("invoice_number")
    sp_addinv.add_argument("date", help="YYYY-MM-DD")
    sp_addinv.add_argument("amount", help="Positive amount")
    sp_addinv.add_argument("--notes", default=None)

    sp_addpay = sub.add_parser("add-payment", help="Add payment to a vendor account")
    sp_addpay.add_argument("canonical_vendor")
    sp_addpay.add_argument("date", help="YYYY-MM-DD")
    sp_addpay.add_argument("amount", help="Amount (positive or negative; stored as negative)")
    sp_addpay.add_argument("--ref", default=None, help="Check number or external reference")
    sp_addpay.add_argument("--notes", default=None)

    sp_list = sub.add_parser("list-accounts", help="List vendor accounts")

    sp_ledger = sub.add_parser("ledger", help="Show ledger for a vendor account")
    sp_ledger.add_argument("canonical_vendor")

    args = ap.parse_args()

    conn, cur = conn_cur()
    try:
        if args.cmd == "add-account":
            acc_id = ensure_account(cur, args.canonical_vendor.upper(), args.display_name)
            conn.commit()
            print(f"Account ensured: id={acc_id} vendor={args.canonical_vendor.upper()}")
        elif args.cmd == "add-invoice":
            acc_id = get_account_id(cur, args.canonical_vendor.upper())
            if not acc_id:
                acc_id = ensure_account(cur, args.canonical_vendor.upper(), args.canonical_vendor.upper())
            led_id = add_invoice(cur, acc_id, parse_date(args.date), parse_amount(args.amount), args.invoice_number, args.notes)
            conn.commit()
            print(f"Invoice added: ledger_id={led_id} account_id={acc_id}")
        elif args.cmd == "add-payment":
            acc_id = get_account_id(cur, args.canonical_vendor.upper())
            if not acc_id:
                acc_id = ensure_account(cur, args.canonical_vendor.upper(), args.canonical_vendor.upper())
            led_id = add_payment(cur, acc_id, parse_date(args.date), parse_amount(args.amount), args.ref, args.notes)
            conn.commit()
            print(f"Payment added: ledger_id={led_id} account_id={acc_id}")
        elif args.cmd == "list-accounts":
            rows = list_accounts(cur)
            for aid, canon, disp in rows:
                print(f"{aid} | {canon} | {disp or ''}")
        elif args.cmd == "ledger":
            acc_id = get_account_id(cur, args.canonical_vendor.upper())
            if not acc_id:
                print("No such vendor account")
            else:
                entries = ledger_for_account(cur, acc_id)
                print(f"Ledger for {args.canonical_vendor.upper()} (account_id={acc_id}):")
                for d, t, a, ref, n, bal in entries:
                    print(f"{d} | {t:<9} | {a:+.2f} | ref={ref or ''} | bal={bal:+.2f} | {n or ''}")
        else:
            ap.print_help()
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
