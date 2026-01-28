import os
import sys
import csv
import argparse
from datetime import datetime, timedelta

# Vendor payment-receipt matching without QuickBooks.
# Matches receipts (vendor invoices) to bank transactions (payments out)
# using vendor name normalization, amount, and date windows.
# Default: dry-run producing CSV under reports; optional DB linkage if tables exist.

VENDOR_SYNONYMS = {
    "106.7 THE DRIVE": {"THE DRIVE", "106.7 THE DRIVE", "DRIVE"},
    "FIBRENEW": {"FIBRENEW", "FIBRENEW CALGARY", "FIBRENEW-CALGARY"},
    "ROGERS": {"ROGERS", "ROGERS COMMUNICATIONS"},
    "TELUS": {"TELUS", "TELUS MOBILITY"},
}

DEFAULT_VENDOR_SET = set(VENDOR_SYNONYMS.keys())


def normalize_vendor(v: str) -> str:
    return (v or "").strip().upper()


def description_matches_vendor(desc: str, vendor_key: str) -> bool:
    desc_up = (desc or "").upper()
    synonyms = VENDOR_SYNONYMS.get(vendor_key, {vendor_key})
    return any(s in desc_up for s in synonyms)


def fetch_db_rows(cur, query, params=None):
    cur.execute(query, params or ())
    return cur.fetchall()


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


def load_receipts(cur, vendor_filter: set):
    # Minimal fields used: receipt_id, receipt_date, vendor_name, gross_amount, description
    rows = []
    try:
        res = fetch_db_rows(cur, "SELECT receipt_id, receipt_date, vendor_name, gross_amount, description FROM receipts WHERE vendor_name IS NOT NULL")
        for r in res:
            rid, rdate, vname, amt, desc = r
            v_norm = normalize_vendor(vname)
            if vendor_filter and v_norm not in vendor_filter:
                continue
            rows.append({
                "receipt_id": rid,
                "receipt_date": rdate,
                "vendor_name": v_norm,
                "gross_amount": float(amt or 0),
                "description": desc or "",
            })
    except Exception as e:
        print(f"WARN: receipts query failed: {e}")
    return rows


def detect_bank_schema(cur):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='banking_transactions'
    """)
    cols = {r[0] for r in cur.fetchall()}
    id_col = 'id' if 'id' in cols else ('banking_transaction_id' if 'banking_transaction_id' in cols else ('transaction_id' if 'transaction_id' in cols else None))
    date_col = 'transaction_date' if 'transaction_date' in cols else ('date' if 'date' in cols else ('posted_date' if 'posted_date' in cols else None))
    desc_col = 'description' if 'description' in cols else ('details' if 'details' in cols else ('memo' if 'memo' in cols else None))
    # Determine amount column or expression
    amount_col = 'amount' if 'amount' in cols else None
    amount_expr = None
    if not amount_col:
        # Common alternatives
        if 'amount_cad' in cols:
            amount_col = 'amount_cad'
        elif 'value' in cols:
            amount_col = 'value'
        elif ('credit' in cols or 'debit' in cols) or ('credit_amount' in cols or 'debit_amount' in cols):
            # Compose net amount: credit - debit (deposits positive, payments negative)
            credit = 'credit_amount' if 'credit_amount' in cols else 'credit'
            debit = 'debit_amount' if 'debit_amount' in cols else 'debit'
            amount_expr = f"(COALESCE({credit},0) - COALESCE({debit},0)) AS amount"
    acct_col = 'mapped_bank_account_id' if 'mapped_bank_account_id' in cols else None
    return {
        'id': id_col,
        'date': date_col,
        'desc': desc_col,
        'amount': amount_col,
        'amount_expr': amount_expr,
        'acct': acct_col,
        'has_table': len(cols) > 0,
    }

def load_bank_tx(cur):
    # Minimal fields used: id, transaction_date, amount, description, mapped_bank_account_id
    rows = []
    try:
        schema = detect_bank_schema(cur)
        if not (schema['id'] and schema['date'] and (schema['amount'] or schema['amount_expr']) and schema['desc']):
            raise RuntimeError(f"banking_transactions schema unknown: {schema}")
        amount_select = schema['amount'] if schema['amount'] else schema['amount_expr']
        select_cols = ", ".join([
            schema['id'], schema['date'], amount_select, schema['desc']
        ] + ([schema['acct']] if schema['acct'] else []))
        res = fetch_db_rows(cur, f"SELECT {select_cols} FROM banking_transactions")
        for r in res:
            if schema['acct']:
                bid, bdate, amt, desc, acct = r
            else:
                bid, bdate, amt, desc = r
                acct = None
            rows.append({
                "bank_tx_id": bid,
                "transaction_date": bdate,
                "amount": float(amt or 0),
                "description": desc or "",
                "mapped_bank_account_id": acct,
            })
    except Exception as e:
        print(f"WARN: banking_transactions query failed: {e}")
    return rows


def match_vendor_receipts_to_bank(receipts, bank_tx, window_days: int):
    # Only consider outflow payments (amount < 0)
    outflows = [b for b in bank_tx if b["amount"] < 0]

    matches = []
    for r in receipts:
        target_amt = -abs(r["gross_amount"])  # receipts are positive, bank outflows negative
        rdate = r["receipt_date"]
        if isinstance(rdate, datetime):
            rdate = rdate.date()
        start = rdate - timedelta(days=0)
        end = rdate + timedelta(days=window_days)

        # candidate bank transactions by amount equality and date window
        def to_date(x):
            return x.date() if isinstance(x, datetime) else x
        candidates = [
            b for b in outflows
            if abs(b["amount"] - target_amt) < 0.005 and start <= to_date(b["transaction_date"]) <= end
        ]
        # rank by description vendor match, then nearest date
        scored = []
        for b in candidates:
            vendor_key = r["vendor_name"]
            desc_match = description_matches_vendor(b["description"], vendor_key)
            date_diff = abs((to_date(b["transaction_date"]) - rdate).days)
            score = (1 if desc_match else 0, -date_diff)
            scored.append((score, b))
        scored.sort(key=lambda x: x[0], reverse=True)

        if scored:
            best_b = scored[0][1]
            confidence = 0.9 if description_matches_vendor(best_b["description"], r["vendor_name"]) else 0.7
            matches.append({
                "receipt_id": r["receipt_id"],
                "receipt_date": rdate.isoformat(),
                "vendor_name": r["vendor_name"],
                "gross_amount": f"{r['gross_amount']:.2f}",
                "bank_tx_id": best_b["bank_tx_id"],
                "bank_date": to_date(best_b["transaction_date"]).isoformat(),
                "bank_amount": f"{best_b['amount']:.2f}",
                "bank_desc": best_b["description"],
                "confidence": f"{confidence:.2f}",
                "rule": f"amount==, within {window_days}d, vendor_desc={'Y' if confidence>0.8 else 'N'}",
            })
        else:
            matches.append({
                "receipt_id": r["receipt_id"],
                "receipt_date": rdate.isoformat(),
                "vendor_name": r["vendor_name"],
                "gross_amount": f"{r['gross_amount']:.2f}",
                "bank_tx_id": "",
                "bank_date": "",
                "bank_amount": "",
                "bank_desc": "",
                "confidence": "0.00",
                "rule": f"no-match within {window_days}d",
            })
    return matches


def write_csv(matches, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = [
        "receipt_id",
        "receipt_date",
        "vendor_name",
        "gross_amount",
        "bank_tx_id",
        "bank_date",
        "bank_amount",
        "bank_desc",
        "confidence",
        "rule",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for m in matches:
            w.writerow(m)


def maybe_write_db_links(conn, matches, write: bool):
    if not write:
        return False, "Dry-run: no DB writes"
    try:
        cur = conn.cursor()
        # Detect ledger table existence
        cur.execute("""
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables 
              WHERE table_schema='public' AND table_name='banking_receipt_matching_ledger'
            )
        """)
        has_ledger = cur.fetchone()[0]
        writes = 0
        for m in matches:
            if not m["bank_tx_id"]:
                continue
            rid = m["receipt_id"]
            bid = m["bank_tx_id"]
            if has_ledger:
                cur.execute("""
                    INSERT INTO banking_receipt_matching_ledger (receipt_id, banking_transaction_id, match_confidence, match_rule)
                    SELECT %s, %s, %s, %s
                    WHERE NOT EXISTS (
                      SELECT 1 FROM banking_receipt_matching_ledger 
                      WHERE receipt_id=%s AND banking_transaction_id=%s
                    )
                """, (rid, bid, float(m["confidence"]), m["rule"], rid, bid))
                writes += cur.rowcount
            else:
                # Try direct column on receipts
                cur.execute("""
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.columns 
                      WHERE table_schema='public' AND table_name='receipts' AND column_name='banking_transaction_id'
                    )
                """)
                has_col = cur.fetchone()[0]
                if has_col:
                    cur.execute("""
                        UPDATE receipts r SET banking_transaction_id=%s 
                        WHERE r.receipt_id=%s AND (r.banking_transaction_id IS NULL OR r.banking_transaction_id=%s)
                    """, (bid, rid, bid))
                    writes += cur.rowcount
        conn.commit()
        return True, f"DB writes committed: {writes} links"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, f"DB write failed: {e}"


def main():
    ap = argparse.ArgumentParser(description="Link vendor receipts to bank payments (dry-run by default)")
    ap.add_argument("--vendors", nargs="*", default=list(DEFAULT_VENDOR_SET), help="Vendor keys to include (uppercase)")
    ap.add_argument("--window-days", type=int, default=30, help="Match window in days from receipt date")
    ap.add_argument("--write", action="store_true", help="Write links to DB if ledger/column exists")
    args = ap.parse_args()

    vendors = {normalize_vendor(v) for v in args.vendors}

    conn = try_db_connect()
    receipts = []
    bank_tx = []
    if conn:
        try:
            cur = conn.cursor()
            receipts = load_receipts(cur, vendors)
            bank_tx = load_bank_tx(cur)
            cur.close()
        except Exception as e:
            print(f"WARN: DB queries failed: {e}")
    else:
        print("INFO: DB unavailable; no matches will be produced.")

    matches = match_vendor_receipts_to_bank(receipts, bank_tx, args.window_days) if receipts and bank_tx else []

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    out_csv = os.path.join(repo_root, "reports", "VENDOR_PAYMENT_RECEIPT_LINKS.csv")
    write_csv(matches, out_csv)

    wrote, msg = (False, "No DB attempt")
    if conn:
        wrote, msg = maybe_write_db_links(conn, matches, args.write)
        conn.close()

    print(f"CSV: {out_csv}")
    print(msg)
    print(f"Total receipts considered: {len(receipts)}; matches: {sum(1 for m in matches if m.get('bank_tx_id'))}")


if __name__ == "__main__":
    main()
