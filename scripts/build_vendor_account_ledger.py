import os
import csv
from datetime import datetime, date
from typing import List, Dict

# Build per-vendor account ledgers from receipts and bank transactions.
# Dry-run only: writes CSVs and summaries under reports/vendor_accounts.
# No QuickBooks. Uses ALMS DB tables: receipts, banking_transactions.

VENDOR_SYNONYMS = {
    "106.7 THE DRIVE": {"THE DRIVE", "106.7 THE DRIVE", "DRIVE"},
    "FIBRENEW": {"FIBRENEW", "FIBRENEW CALGARY", "FIBRENEW-CALGARY"},
    "ROGERS": {"ROGERS", "ROGERS COMMUNICATIONS", "ROGERS WIRELESS"},
    "TELUS": {"TELUS", "TELUS MOBILITY", "TELUS INTERNET"},
}

DEFAULT_VENDOR_SET = list(VENDOR_SYNONYMS.keys())


def normalize_vendor(v: str) -> str:
    return (v or "").strip().upper()


def description_matches_vendor(desc: str, vendor_key: str) -> bool:
    if not desc:
        return False
    desc_up = desc.upper()
    synonyms = VENDOR_SYNONYMS.get(vendor_key, {vendor_key})
    return any(s in desc_up for s in synonyms)


def try_db_connect():
    try:
        import psycopg2
        DB_HOST = os.environ.get("DB_HOST", "localhost")
        DB_NAME = os.environ.get("DB_NAME", "almsdata")
        DB_USER = os.environ.get("DB_USER", "postgres")
        DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
        return conn
    except Exception as e:
        print(f"WARN: DB connect failed: {e}")
        return None


def load_receipts(cur) -> List[Dict]:
    rows = []
    try:
        cur.execute("""
            SELECT receipt_id, receipt_date, vendor_name, canonical_vendor, gross_amount, category, description
            FROM receipts
            WHERE vendor_name IS NOT NULL AND receipt_date IS NOT NULL
        """)
        for r in cur.fetchall():
            rid, rdate, vname, canon, amt, cat, desc = r
            rows.append({
                "receipt_id": rid,
                "receipt_date": rdate,
                "vendor_name": normalize_vendor(vname),
                "canonical_vendor": normalize_vendor(canon) if canon else None,
                "gross_amount": float(amt or 0),
                "category": cat or "",
                "description": desc or "",
            })
    except Exception as e:
        print(f"WARN: load_receipts failed: {e}")
    return rows


def load_bank_tx(cur) -> List[Dict]:
    rows = []
    try:
        # Use credit_amount - debit_amount as net amount (positive=deposit, negative=payment)
        cur.execute("""
            SELECT transaction_id, transaction_date, description,
                   COALESCE(credit_amount,0) - COALESCE(debit_amount,0) AS amount,
                   check_number, check_recipient
            FROM banking_transactions
            WHERE transaction_date IS NOT NULL
        """)
        for r in cur.fetchall():
            tid, tdate, desc, amt, chk, recip = r
            rows.append({
                "transaction_id": tid,
                "transaction_date": tdate,
                "description": desc or "",
                "amount": float(amt or 0),
                "check_number": (chk or "").strip() if chk else "",
                "check_recipient": (recip or "").strip() if recip else "",
            })
    except Exception as e:
        print(f"WARN: load_bank_tx failed: {e}")
    return rows


def to_date(x):
    return x.date() if isinstance(x, datetime) else x


def build_ledger_for_vendor(vendor_key: str, receipts: List[Dict], bank_tx: List[Dict]):
    # Filter vendor receipts by canonical_vendor or vendor_name synonyms
    r_vendor = []
    for r in receipts:
        canon = r["canonical_vendor"] or r["vendor_name"]
        if canon == vendor_key or description_matches_vendor(r["vendor_name"], vendor_key):
            r_vendor.append(r)

    # Filter bank outflow payments for this vendor
    b_vendor = []
    for b in bank_tx:
        if b["amount"] < 0 and description_matches_vendor(b["description"], vendor_key):
            b_vendor.append(b)

    # Events: invoices (+amount), payments (-amount)
    events = []
    for r in r_vendor:
        events.append({
            "date": to_date(r["receipt_date"]),
            "type": "INVOICE",
            "source": "receipts",
            "source_id": r["receipt_id"],
            "description": r["description"],
            "amount": round(r["gross_amount"], 2),
            "confidence": 1.0,
            "note": r.get("category") or "",
        })
    for b in b_vendor:
        conf = 0.9 if description_matches_vendor(b["description"], vendor_key) else 0.6
        events.append({
            "date": to_date(b["transaction_date"]),
            "type": "PAYMENT",
            "source": "banking_transactions",
            "source_id": b["transaction_id"],
            "description": b["description"],
            "amount": round(b["amount"], 2),  # negative
            "confidence": conf,
            "note": b.get("check_number") or "",
        })

    # Sort by date, then payments after invoices on same day
    events.sort(key=lambda e: (e["date"], 0 if e["type"] == "INVOICE" else 1, e["source"]))

    # Running balance: invoices increase, payments decrease
    balance = 0.0
    for e in events:
        balance = round(balance + e["amount"], 2)
        e["balance_after"] = f"{balance:.2f}"

    return events, balance, r_vendor, b_vendor


def write_vendor_outputs(vendor_key: str, events: List[Dict], final_balance: float, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"{vendor_key.replace(' ', '_')}_LEDGER.csv")
    txt_path = os.path.join(out_dir, f"{vendor_key.replace(' ', '_')}_SUMMARY.txt")

    fieldnames = [
        "date", "type", "source", "source_id", "description", "amount", "balance_after", "confidence", "note"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for e in events:
            row = e.copy()
            row["date"] = row["date"].isoformat()
            row["amount"] = f"{row['amount']:.2f}"
            row["confidence"] = f"{row['confidence']:.2f}"
            w.writerow(row)

    lines = []
    lines.append(f"VENDOR ACCOUNT LEDGER: {vendor_key}")
    lines.append("Source: ALMS receipts + banking transactions (paperwork-only)")
    lines.append(f"Entries: {len(events)}")
    lines.append(f"Ending balance: {final_balance:.2f}")
    lines.append("Notes:")
    lines.append("- Balance increases with invoices, decreases with payments.")
    lines.append("- Description vendor match boosts confidence; verify any low-confidence entries.")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return csv_path, txt_path


def main():
    vendors = DEFAULT_VENDOR_SET
    conn = try_db_connect()
    if not conn:
        print("ERROR: DB unavailable; cannot build ledgers.")
        return
    cur = conn.cursor()
    receipts = load_receipts(cur)
    bank_tx = load_bank_tx(cur)
    cur.close()
    conn.close()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    out_dir = os.path.join(repo_root, "reports", "vendor_accounts")
    os.makedirs(out_dir, exist_ok=True)

    total_entries = 0
    for v in vendors:
        events, bal, r_vendor, b_vendor = build_ledger_for_vendor(v, receipts, bank_tx)
        csv_path, txt_path = write_vendor_outputs(v, events, bal, out_dir)
        print(f"{v}: entries={len(events)} ending_balance={bal:.2f}")
        print(csv_path)
        print(txt_path)
        total_entries += len(events)

    print(f"TOTAL ledger entries across vendors: {total_entries}")


if __name__ == "__main__":
    main()
