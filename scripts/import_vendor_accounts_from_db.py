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

VENDOR_SYNONYMS = {
    "FIBRENEW": {"FIBRENEW", "FIBRENEW CALGARY", "FIBRENEW-CALGARY"},
    "ROGERS": {"ROGERS", "ROGERS COMMUNICATIONS", "ROGERS WIRELESS"},
    "TELUS": {"TELUS", "TELUS MOBILITY", "TELUS INTERNET"},
    "106.7 THE DRIVE": {"106.7 THE DRIVE", "THE DRIVE", "DRIVE"},
    "HEFFNER AUTO": {"HEFFNER", "HEFFNER AUTO"},
    "ACE TRUCKING": {"ACE TRUCKING", "ACE-TRUCKING", "ACE"},
    "INSURANCE": {"INSURANCE", "INTACT", "AVIVA", "ALLSTATE", "ECONOMICAL"},
}

DEFAULT_VENDORS = list(VENDOR_SYNONYMS.keys())


def conn_cur():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    return conn, conn.cursor()


def ensure_account(cur, canonical_vendor: str, display_name: str = None):
    cur.execute("""
        INSERT INTO vendor_accounts (canonical_vendor, display_name)
        VALUES (%s, %s)
        ON CONFLICT (canonical_vendor) DO UPDATE SET display_name = COALESCE(EXCLUDED.display_name, vendor_accounts.display_name)
        RETURNING account_id
    """, (canonical_vendor, display_name))
    return cur.fetchone()[0]


def normalize(s: str) -> str:
    return (s or "").strip().upper()


def matches_vendor_text(text: str, vendor_key: str) -> bool:
    if not text:
        return False
    t = text.upper()
    return any(s in t for s in VENDOR_SYNONYMS.get(vendor_key, {vendor_key}))


def load_receipts(cur):
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, gross_amount, description
        FROM receipts
        WHERE receipt_date IS NOT NULL
    """)
    rows = []
    for rid, rdate, vname, canon, amt, desc in cur.fetchall():
        rows.append({
            "receipt_id": rid,
            "receipt_date": rdate,
            "vendor_name": normalize(vname),
            "canonical_vendor": normalize(canon) if canon else None,
            "gross_amount": Decimal(str(amt or 0)),
            "description": desc or "",
        })
    return rows


def load_bank_tx(cur):
    # Net amount: credit_amount - debit_amount (payments are negative)
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               COALESCE(credit_amount,0) - COALESCE(debit_amount,0) AS amount,
               check_number
        FROM banking_transactions
        WHERE transaction_date IS NOT NULL
    """)
    rows = []
    for tid, tdate, desc, amt, chk in cur.fetchall():
        rows.append({
            "transaction_id": tid,
            "transaction_date": tdate,
            "description": desc or "",
            "amount": Decimal(str(amt or 0)),
            "check_number": (chk or "").strip() if chk else "",
        })
    return rows


def upsert_invoice(cur, account_id: int, r: dict, apply: bool) -> bool:
    # INVOICE: positive amount
    cur.execute("""
        INSERT INTO vendor_account_ledger (account_id, entry_date, entry_type, amount, source_table, source_id, notes)
        VALUES (%s, %s, 'INVOICE', %s, 'receipts', %s, %s)
        ON CONFLICT (account_id, source_table, source_id) DO NOTHING
        RETURNING ledger_id
    """, (account_id, r["receipt_date"], r["gross_amount"], str(r["receipt_id"]), r["description"]))
    row = cur.fetchone()
    return bool(row)


def upsert_payment(cur, account_id: int, b: dict, vendor_key: str, apply: bool) -> bool:
    if b["amount"] >= 0:
        return False
    conf = Decimal("0.90") if matches_vendor_text(b["description"], vendor_key) else Decimal("0.60")
    cur.execute("""
        INSERT INTO vendor_account_ledger (account_id, entry_date, entry_type, amount, source_table, source_id, external_ref, match_confidence, notes)
        VALUES (%s, %s, 'PAYMENT', %s, 'banking_transactions', %s, %s, %s, %s)
        ON CONFLICT (account_id, source_table, source_id) DO NOTHING
        RETURNING ledger_id
    """, (account_id, b["transaction_date"], b["amount"], str(b["transaction_id"]), b["check_number"], conf, b["description"]))
    row = cur.fetchone()
    return bool(row)


def recompute_balance_after(cur, account_id: int):
    # Compute running balance ordered by date then ledger_id
    cur.execute("""
        SELECT ledger_id, entry_date, entry_type, amount
        FROM vendor_account_ledger
        WHERE account_id=%s
        ORDER BY entry_date ASC, CASE WHEN entry_type='INVOICE' THEN 0 ELSE 1 END, ledger_id ASC
    """, (account_id,))
    rows = cur.fetchall()
    bal = Decimal("0.00")
    for lid, d, t, a in rows:
        bal += Decimal(a)
        cur.execute("UPDATE vendor_account_ledger SET balance_after=%s WHERE ledger_id=%s", (bal, lid))
    return bal


def main():
    ap = argparse.ArgumentParser(description="Import vendor accounts from receipts and banking (idempotent)")
    ap.add_argument("--vendors", nargs="*", default=DEFAULT_VENDORS, help="Vendor keys to import")
    ap.add_argument("--apply", action="store_true", help="Write to DB (default is dry-run)")
    args = ap.parse_args()

    vendors = [normalize(v) for v in args.vendors]
    conn, cur = conn_cur()
    receipts = load_receipts(cur)
    bank_tx = load_bank_tx(cur)

    total_invoices = 0
    total_payments = 0
    results = []

    try:
        for v in vendors:
            acc_id = ensure_account(cur, v, v)
            # Filter receipts: canonical vendor or vendor_name matching synonyms
            r_list = [r for r in receipts if (r["canonical_vendor"] == v) or matches_vendor_text(r["vendor_name"], v)]
            b_list = [b for b in bank_tx if b["amount"] < 0 and matches_vendor_text(b["description"], v)]

            inserted_inv = 0
            inserted_pay = 0
            for r in r_list:
                if upsert_invoice(cur, acc_id, r, args.apply):
                    inserted_inv += 1
            for b in b_list:
                if upsert_payment(cur, acc_id, b, v, args.apply):
                    inserted_pay += 1

            bal = recompute_balance_after(cur, acc_id) if args.apply else None
            total_invoices += inserted_inv
            total_payments += inserted_pay
            results.append((v, acc_id, len(r_list), len(b_list), inserted_inv, inserted_pay, bal))

        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        cur.close()
        conn.close()

    print("Import Summary:")
    for v, acc_id, rc, bc, ii, ip, bal in results:
        print(f"{v} (account_id={acc_id}): receipts candidates={rc}, payments candidates={bc}, inserted invoices={ii}, inserted payments={ip}, ending balance={(bal if bal is not None else 'DRY-RUN')} ")
    print(f"TOTAL inserted: invoices={total_invoices}, payments={total_payments}")


if __name__ == "__main__":
    main()
