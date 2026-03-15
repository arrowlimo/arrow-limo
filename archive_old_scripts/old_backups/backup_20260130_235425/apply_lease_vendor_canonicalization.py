import os
import sys
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

# Confidence threshold for applying canonicalization
CONFIDENCE_THRESHOLD = 0.80
# Prefer exact amount matches across a wider window
DATE_WINDOW_DAYS = 45

REPORT_DIR = os.path.join("l:\\limo", "reports")
SUMMARY_PATH = os.path.join(REPORT_DIR, "LEASE_CANONICALIZATION_APPLY_SUMMARY.txt")
DETAIL_PATH = os.path.join(REPORT_DIR, "LEASE_CANONICALIZATION_APPLY_DETAILS.csv")

def norm(s: str) -> str:
    return (s or "").strip()

CANONICAL_MAP_KEYWORDS = [
    # Lease Finance Group variants
    ("LEASE FINANCE GROUP", "LEASE FINANCE GROUP"),
    ("LEASE FINANCE GR", "LEASE FINANCE GROUP"),
    ("LFG BUSINESS PAD", "LEASE FINANCE GROUP"),
    ("LFG", "LEASE FINANCE GROUP"),

    # PAD indicators
    ("PRE AUTH", "PRE AUTHORIZED DEBIT"),
    ("PRE-AUTH", "PRE AUTHORIZED DEBIT"),
    ("PREAUTHORIZED", "PRE AUTHORIZED DEBIT"),
    ("PRE AUTHORIZED DEBIT", "PRE AUTHORIZED DEBIT"),

    # Jack Carter lease variants
    ("JACK CARTER", "JACK CARTER"),
    ("AUTO LEASE JACK CARTER", "JACK CARTER"),
    ("RENT/LEASE JACK CARTER", "JACK CARTER"),
    ("AUTO LEASE PAYMENT", "JACK CARTER"),

    # Roynat
    ("ROYNAT LEASE FINANCE", "ROYNAT LEASE FINANCE"),
    ("ROYNAT", "ROYNAT LEASE FINANCE"),
]

EXCLUDE_GENERIC = {"LEASE"}

def infer_canonical_from_description(desc: str):
    d = (desc or "").upper()
    for kw, canon in CANONICAL_MAP_KEYWORDS:
        if kw in d:
            return canon, 0.95
    # No strong match
    return None, 0.0


def connect():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def get_account_id(cur, canonical_vendor: str):
    # Lookup by canonical_vendor
    cur.execute(
        """
        SELECT account_id FROM vendor_accounts WHERE UPPER(canonical_vendor) = UPPER(%s)
        """,
        (canonical_vendor,),
    )
    r = cur.fetchone()
    if r:
        return r[0]
    # Create account if missing (store display_name same as canonical by default)
    cur.execute(
        """
        INSERT INTO vendor_accounts (canonical_vendor, display_name, created_at)
        VALUES (%s, %s, NOW())
        RETURNING account_id
        """,
        (canonical_vendor, canonical_vendor),
    )
    return cur.fetchone()[0]


def get_lease_account_id(cur):
    return get_account_id(cur, "LEASE")


def fetch_lease_invoices(cur, lease_account_id: int):
    cur.execute(
        """
        SELECT val.ledger_id, val.account_id, val.source_table, val.source_id,
               val.entry_date, val.amount,
               r.description,
               r.receipt_id, r.vendor_name, r.canonical_vendor
        FROM vendor_account_ledger val
        LEFT JOIN receipts r ON (val.source_table = 'receipts' AND r.receipt_id::text = val.source_id)
        WHERE val.account_id = %s AND val.amount > 0
        ORDER BY val.entry_date
        """,
        (lease_account_id,),
    )
    rows = cur.fetchall()
    return [
        {
            "ledger_id": r[0],
            "account_id": r[1],
            "source_table": r[2],
            "source_id": r[3],
            "entry_date": r[4],
            "amount": float(r[5] or 0.0),
            "description": norm(r[6]),
            "receipt_id": r[7],
            "receipt_vendor": norm(r[8]),
            "receipt_canonical": norm(r[9]),
        }
        for r in rows
    ]


def fetch_bank_transactions(cur, start_date: datetime, end_date: datetime):
    cur.execute(
        """
        SELECT transaction_id, transaction_date, description,
               COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0) AS net_amount
        FROM banking_transactions
        WHERE transaction_date BETWEEN %s AND %s
        ORDER BY transaction_date
        """,
        (start_date, end_date),
    )
    rows = cur.fetchall()
    return [
        {
            "transaction_id": r[0],
            "transaction_date": r[1],
            "description": norm(r[2]),
            "net_amount": float(r[3] or 0.0),
        }
        for r in rows
    ]


def match_payment_for_invoice(inv, bank_rows):
    """Find payment candidates by exact net amount first, within a wider window."""
    target_amt = -abs(inv["amount"])  # payment is money out
    d = inv["entry_date"]
    window_start = d - timedelta(days=DATE_WINDOW_DAYS)
    window_end = d + timedelta(days=DATE_WINDOW_DAYS)

    # Exact amount matches within window
    exact = [
        b for b in bank_rows
        if window_start <= b["transaction_date"] <= window_end and abs(b["net_amount"] - target_amt) < 0.005
    ]
    if exact:
        # Prefer rows whose description yields a canonical vendor
        exact.sort(
            key=lambda x: (
                infer_canonical_from_description(x["description"])[0] is not None,
                x["description"] != "",
                x["transaction_date"]
            ),
            reverse=True,
        )
        return exact[0]

    # If no exact match, do not attempt fuzzy amount matching; skip
    return None


def recompute_account_balances(cur, account_ids):
    for acc_id in set(account_ids):
        # Recompute running balances in entry_date order
        cur.execute(
            """
            SELECT ledger_id, amount FROM vendor_account_ledger
            WHERE account_id = %s
            ORDER BY entry_date, ledger_id
            """,
            (acc_id,),
        )
        total = 0.0
        rows = cur.fetchall()
        for ledger_id, amount in rows:
            total += float(amount or 0.0)
            cur.execute(
                "UPDATE vendor_account_ledger SET balance_after = %s WHERE ledger_id = %s",
                (round(total, 2), ledger_id),
            )


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    applied = 0
    skipped = 0
    created_accounts = set()
    affected_accounts = set()

    try:
        lease_id = get_lease_account_id(cur)
        # Fetch a broad bank window to allow matching across periods
        cur.execute("SELECT MIN(entry_date), MAX(entry_date) FROM vendor_account_ledger WHERE account_id = %s", (lease_id,))
        r = cur.fetchone()
        start_date = r[0] or datetime(2010, 1, 1)
        end_date = r[1] or datetime(2030, 1, 1)
        bank_rows = fetch_bank_transactions(cur, start_date - timedelta(days=DATE_WINDOW_DAYS), end_date + timedelta(days=DATE_WINDOW_DAYS))
        invoices = fetch_lease_invoices(cur, lease_id)

        detail_rows = []

        for inv in invoices:
            match = match_payment_for_invoice(inv, bank_rows)
            if not match:
                skipped += 1
                detail_rows.append([
                    inv["ledger_id"], inv["source_id"], inv["entry_date"], inv["amount"], inv["description"],
                    "", "", "NO_MATCH", inv["receipt_id"] or "", inv["receipt_vendor"], inv["receipt_canonical"], "SKIPPED"
                ])
                continue
            canon, conf = infer_canonical_from_description(match["description"])
            if not canon or conf < CONFIDENCE_THRESHOLD or canon in EXCLUDE_GENERIC:
                skipped += 1
                detail_rows.append([
                    inv["ledger_id"], inv["source_id"], inv["entry_date"], inv["amount"], inv["description"],
                    match["transaction_id"], match["description"], f"CONF={conf:.2f}", inv["receipt_id"] or "", inv["receipt_vendor"], inv["receipt_canonical"], "SKIPPED"
                ])
                continue

            target_acc_id = get_account_id(cur, canon)
            created_accounts.add(canon)
            affected_accounts.update({lease_id, target_acc_id})

            # Update receipts.canonical_vendor when present
            if inv["receipt_id"]:
                cur.execute(
                    """
                    UPDATE receipts SET canonical_vendor = %s
                    WHERE receipt_id = %s AND (canonical_vendor IS NULL OR canonical_vendor = 'LEASE')
                    """,
                    (canon, inv["receipt_id"]),
                )

            # Move invoice ledger entry to target account
            cur.execute(
                "UPDATE vendor_account_ledger SET account_id = %s WHERE ledger_id = %s AND account_id = %s",
                (target_acc_id, inv["ledger_id"], lease_id),
            )

            # If the matched banking transaction is currently under LEASE, move it too.
            cur.execute(
                """
                UPDATE vendor_account_ledger SET account_id = %s
                WHERE source_table = 'banking_transactions' AND source_id = %s AND account_id = %s
                """,
                (target_acc_id, str(match["transaction_id"]), lease_id),
            )

            applied += 1
            detail_rows.append([
                inv["ledger_id"], inv["source_id"], inv["entry_date"], inv["amount"], inv["description"],
                match["transaction_id"], match["description"], f"CONF={conf:.2f}", inv["receipt_id"] or "", inv["receipt_vendor"], canon, "APPLIED"
            ])

        # Recompute balances for affected accounts
        recompute_account_balances(cur, affected_accounts)

        conn.commit()

        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            f.write(f"Applied canonicalizations: {applied}\n")
            f.write(f"Skipped: {skipped}\n")
            if created_accounts:
                f.write("Accounts created/used:\n")
                for a in sorted(created_accounts):
                    f.write(f" - {a}\n")

        with open(DETAIL_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "ledger_id", "source_id", "entry_date", "amount", "invoice_desc",
                "bank_tx_id", "bank_desc", "confidence", "receipt_id", "receipt_vendor", "canonical_vendor", "status"
            ])
            writer.writerows(detail_rows)

        print(f"✅ Applied {applied}, skipped {skipped}. Summary: {SUMMARY_PATH}")

    except Exception as e:
        conn.rollback()
        print(f"❌ Rolled back: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
