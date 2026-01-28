import os
import csv
from datetime import datetime, timedelta, date
from decimal import Decimal
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

OUT_DIR = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)), "reports")
CSV_PATH = os.path.join(OUT_DIR, "LEASE_VENDOR_ENRICHMENT_AUDIT.csv")
TXT_PATH = os.path.join(OUT_DIR, "LEASE_VENDOR_ENRICHMENT_SUMMARY.txt")

GENERIC_TOKENS = {
    "BANK","TRANSFER","ATM","FEE","NSF","DEPOSIT","SERVICE","ACCOUNT","BRANCH","PAYMENT",
    "VCARD","MCARD","VISA","MASTERCARD","MERCHANT","SQUARE"
}

VENDOR_HINTS = {
    # Auto finance/leasing common
    "TOYOTA": "TOYOTA FINANCIAL",
    "FORD CREDIT": "FORD CREDIT",
    "HONDA": "HONDA FINANCIAL",
    "GM FINANCIAL": "GM FINANCIAL",
    "RBC": "RBC",
    "ROYAL BANK": "RBC",
    "TD": "TD FINANCING SERVICES",
    "CIBC": "CIBC",
    "BMO": "BMO",
    "SCOTIA": "SCOTIABANK",
    "SCOTIABANK": "SCOTIABANK",
    "LEASE": "LEASE",
    "HEFFNER": "HEFFNER AUTO",
    "ACE": "ACE TRUCKING",
}

WINDOW_DAYS = 10


def conn_cur():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    return conn, conn.cursor()


def get_lease_account_id(cur):
    cur.execute("SELECT account_id FROM vendor_accounts WHERE canonical_vendor=%s", ("LEASE",))
    row = cur.fetchone()
    return row[0] if row else None


def get_lease_invoices(cur, lease_account_id):
    # Pull ledger invoices for LEASE account and join back to receipts if available
    cur.execute("""
        SELECT l.ledger_id, l.entry_date, l.amount, l.source_table, l.source_id,
               r.receipt_id, r.vendor_name, r.canonical_vendor, r.description
        FROM vendor_account_ledger l
        LEFT JOIN receipts r ON (l.source_table='receipts' AND r.receipt_id::text = l.source_id)
        WHERE l.account_id=%s AND l.entry_type='INVOICE'
        ORDER BY l.entry_date ASC, l.ledger_id ASC
    """, (lease_account_id,))
    rows = []
    for lid, d, amt, st, sid, rid, vname, canon, desc in cur.fetchall():
        rows.append({
            "ledger_id": lid,
            "date": d,
            "amount": Decimal(str(amt or 0)),
            "source_table": st,
            "source_id": sid,
            "receipt_id": rid,
            "vendor_name": (vname or "").strip().upper() if vname else "",
            "canonical_vendor": (canon or "").strip().upper() if canon else "",
            "receipt_desc": desc or "",
        })
    return rows


def load_bank_tx(cur):
    # Net amount: positive deposit, negative payment
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               COALESCE(credit_amount,0) - COALESCE(debit_amount,0) AS amount,
               vendor_extracted
        FROM banking_transactions
        WHERE transaction_date IS NOT NULL
    """)
    rows = []
    for tid, tdate, desc, amt, vend in cur.fetchall():
        rows.append({
            "transaction_id": tid,
            "date": tdate,
            "description": desc or "",
            "amount": Decimal(str(amt or 0)),
            "vendor_extracted": (vend or "").strip().upper(),
        })
    return rows


def infer_vendor_from_desc(desc: str):
    d = (desc or "").upper()
    for key, canon in VENDOR_HINTS.items():
        if key in d:
            # avoid purely generic tokens
            if key in GENERIC_TOKENS:
                continue
            return canon
    return None


def is_generic_word(word: str) -> bool:
    return word in GENERIC_TOKENS or len(word) < 3


def first_meaningful_token(desc: str):
    tokens = [t for t in (desc or "").upper().replace("*"," ").replace("-"," ").split() if t.isalpha()]
    for t in tokens:
        if not is_generic_word(t):
            return t
    return None


def match_payments(invoices, bank_tx):
    events = []
    for inv in invoices:
        inv_date = inv["date"]
        start = inv_date - timedelta(days=0)
        end = inv_date + timedelta(days=WINDOW_DAYS)
        target = inv["amount"]
        # match negative payments with equal magnitude
        candidates = [b for b in bank_tx if b["amount"] < 0 and abs(b["amount"] + target) < Decimal("0.01") and start <= b["date"] <= end]
        # score by vendor inference and proximity
        scored = []
        for b in candidates:
            inferred = infer_vendor_from_desc(b["description"]) or (b["vendor_extracted"] if b["vendor_extracted"] else first_meaningful_token(b["description"]))
            date_diff = abs((b["date"] - inv_date).days)
            score = 0
            if inferred:
                score += 2
            score += max(0, 10 - date_diff)
            scored.append((score, b, inferred))
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0] if scored else None
        if best:
            _, b, inferred = best
            confidence = Decimal("0.90") if inferred and inferred not in GENERIC_TOKENS else Decimal("0.70")
            events.append({
                "ledger_id": inv["ledger_id"],
                "invoice_date": inv_date.isoformat(),
                "invoice_amount": f"{inv['amount']:.2f}",
                "receipt_vendor": inv["vendor_name"],
                "receipt_canonical": inv["canonical_vendor"],
                "receipt_desc": inv["receipt_desc"],
                "bank_tx_id": b["transaction_id"],
                "bank_date": b["date"].isoformat(),
                "bank_desc": b["description"],
                "bank_vendor_extracted": b["vendor_extracted"],
                "inferred_vendor": inferred or "",
                "confidence": f"{confidence:.2f}",
            })
        else:
            events.append({
                "ledger_id": inv["ledger_id"],
                "invoice_date": inv_date.isoformat(),
                "invoice_amount": f"{inv['amount']:.2f}",
                "receipt_vendor": inv["vendor_name"],
                "receipt_canonical": inv["canonical_vendor"],
                "receipt_desc": inv["receipt_desc"],
                "bank_tx_id": "",
                "bank_date": "",
                "bank_desc": "",
                "bank_vendor_extracted": "",
                "inferred_vendor": "",
                "confidence": f"{Decimal('0.00'):.2f}",
            })
    return events


def write_outputs(rows):
    os.makedirs(OUT_DIR, exist_ok=True)
    fields = [
        "ledger_id","invoice_date","invoice_amount","receipt_vendor","receipt_canonical","receipt_desc",
        "bank_tx_id","bank_date","bank_desc","bank_vendor_extracted","inferred_vendor","confidence"
    ]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # Summary
    total = len(rows)
    inferred = sum(1 for r in rows if r["inferred_vendor"])    
    lines = []
    lines.append("LEASE Vendor Enrichment Summary")
    lines.append(f"Total invoices audited: {total}")
    lines.append(f"With inferred vendor via payments: {inferred}")
    top_samples = [r for r in rows if r["inferred_vendor"]][:25]
    lines.append("Samples:")
    for r in top_samples:
        lines.append(f"#{r['ledger_id']} {r['invoice_date']} amt={r['invoice_amount']} inferred={r['inferred_vendor']} bank='{r['bank_desc'][:60]}'")
    with open(TXT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return CSV_PATH, TXT_PATH


def main():
    conn, cur = conn_cur()
    lease_id = get_lease_account_id(cur)
    if not lease_id:
        print("No LEASE vendor account found.")
        return
    invoices = get_lease_invoices(cur, lease_id)
    bank_tx = load_bank_tx(cur)
    conn.close()
    rows = match_payments(invoices, bank_tx)
    csv_path, txt_path = write_outputs(rows)
    print(csv_path)
    print(txt_path)


if __name__ == "__main__":
    main()
