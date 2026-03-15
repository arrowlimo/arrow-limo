#!/usr/bin/env python3
"""
Create CRA-safe receipts for unmatched banking fees/NSF/interest from export JSON.

Behavior:
- Reads the full export JSON (supports nested tables with columns/rows).
- Finds banking_transactions not already linked to receipts or payments.
- Filters to debit-side expenses with classifications: bank_fee, nsf_or_chargeback, interest.
- For each, inserts a receipt (idempotent via source_hash) and links it via
  banking_receipt_matching_ledger (idempotent).

Safety:
- Dry-run by default. Use --write to apply changes.
- Duplicate prevention via receipts.source_hash (sha256 of date+acct+debit+desc).
- Does NOT delete anything.

Usage:
  python -X utf8 scripts/apply_banking_fee_receipts.py --export reports/complete_almsdata_export_20251113.json.gz --limit 200 --write
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from datetime import datetime

import psycopg2


REPORTS_DIR = os.path.join("reports")


def load_export(path: str):
    if not os.path.exists(path):
        gz = path + ".gz" if not path.endswith(".gz") else path
        if os.path.exists(gz):
            path = gz
        else:
            raise FileNotFoundError(f"Export not found: {path}")

    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    else:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def table_to_dicts(node):
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        cols = node.get("columns")
        rows = node.get("rows")
        if isinstance(cols, list) and isinstance(rows, list):
            out = []
            for r in rows:
                if isinstance(r, (list, tuple)):
                    d = {cols[i]: r[i] if i < len(cols) else None for i in range(len(cols))}
                    out.append(d)
                elif isinstance(r, dict):
                    out.append(r)
            return out
    return []


def classify(description: str) -> str:
    d = (description or "").lower()
    if any(k in d for k in ["nsf", "non-sufficient", "returned item", "chargeback", "reversal fee"]):
        return "nsf_or_chargeback"
    if any(k in d for k in ["service charge", "bank fee", "monthly fee", "plan fee", "svc chg", "fee "]):
        return "bank_fee"
    if any(k in d for k in ["interest", "int chg", "overdraft interest"]):
        return "interest"
    return "other"


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def get_db_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REDACTED***')
    )


def main():
    parser = argparse.ArgumentParser(description="Apply receipts for banking fees/NSF/interest")
    parser.add_argument("--export", required=True, help="Path to export JSON (.json or .json.gz)")
    parser.add_argument("--write", action="store_true", help="Apply changes (default dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of inserts")
    parser.add_argument("--account", default=None, help="Restrict to specific account_number")
    args = parser.parse_args()

    data = load_export(args.export)
    table_root = data.get("tables") if isinstance(data, dict) and "tables" in data else data
    banking = table_to_dicts(table_root.get("banking_transactions"))
    receipt_links = table_to_dicts(table_root.get("banking_receipt_matching_ledger"))
    payment_links = table_to_dicts(table_root.get("banking_payment_links"))
    bank_accounts = table_to_dicts(table_root.get("bank_accounts"))

    # Build lookup sets
    linked_receipt_bids = {x.get("banking_transaction_id") for x in receipt_links if x.get("banking_transaction_id") is not None}
    linked_payment_bids = {x.get("banking_transaction_id") for x in payment_links if x.get("banking_transaction_id") is not None}

    # Map account_number -> institution/account_name for vendor label
    acct_name = {}
    for b in bank_accounts:
        acct_num = (b.get("account_number") or "").strip()
        if acct_num:
            inst = (b.get("institution_name") or "").strip() or "Bank"
            acc = (b.get("account_name") or acct_num).strip()
            acct_name[acct_num] = f"{inst} - {acc}"

    # Collect candidates
    candidates = []
    for row in banking:
        tid = row.get("transaction_id")
        if tid in linked_receipt_bids or tid in linked_payment_bids:
            continue
        acct = (row.get("account_number") or "").strip()
        if args.account and acct != args.account:
            continue
        desc = normalize_spaces(row.get("description"))
        debit = float(row.get("debit_amount") or 0)
        credit = float(row.get("credit_amount") or 0)
        date = row.get("transaction_date")
        cls = classify(desc)

        # Only create receipts for expense-side rows we can defend to CRA
        if debit <= 0:
            continue
        if cls not in {"bank_fee", "nsf_or_chargeback", "interest"}:
            continue

        vendor = acct_name.get(acct) or "Bank"
        label = {
            "bank_fee": "Bank Service Charge",
            "nsf_or_chargeback": "NSF/Chargeback Fee",
            "interest": "Bank Interest Charge",
        }[cls]
        rec = {
            "transaction_id": tid,
            "account_number": acct,
            "receipt_date": date,
            "vendor_name": vendor,
            "description": f"{label}: {desc}",
            "currency": "CAD",
            "gross_amount": round(debit, 2),
            "gst_amount": 0.00,
            "net_amount": round(debit, 2),
            "category": "bank",
            "classification": cls,
            "created_from_banking": True,
            "source_system": "BANK",
            "source_reference": f"BANK:{acct}:{tid}",
        }
        # Deterministic hash for idempotency
        key = f"{date}|{acct}|{debit:.2f}|{normalize_spaces(desc).lower()}"
        rec["source_hash"] = sha256_hex(key)
        candidates.append(rec)

    print(f"Proposed receipts: {len(candidates)}")
    if not args.write:
        print("Dry-run: no database changes. Use --write to apply.")
        return

    conn = get_db_conn()
    cur = conn.cursor()

    applied = 0
    for rec in candidates:
        if args.limit and applied >= args.limit:
            break

        # Check if already exists by source_hash
        cur.execute("SELECT receipt_id FROM receipts WHERE source_hash = %s", (rec["source_hash"],))
        row = cur.fetchone()
        if row:
            receipt_id = row[0]
        else:
            # Insert receipt with minimal safe columns
            cur.execute(
                """
                INSERT INTO receipts (
                    receipt_date, vendor_name, description, currency,
                    gross_amount, gst_amount, net_amount, category,
                    created_from_banking, source_system, source_reference, source_hash
                ) VALUES (
                    %s,%s,%s,%s,
                    %s,%s,%s,%s,
                    TRUE,%s,%s,%s
                ) RETURNING receipt_id
                """,
                (
                    rec["receipt_date"], rec["vendor_name"], rec["description"], rec["currency"],
                    rec["gross_amount"], rec["gst_amount"], rec["net_amount"], rec["category"],
                    rec["source_system"], rec["source_reference"], rec["source_hash"]
                )
            )
            receipt_id = cur.fetchone()[0]

        # Link in banking_receipt_matching_ledger if not present
        cur.execute(
            "SELECT 1 FROM banking_receipt_matching_ledger WHERE banking_transaction_id = %s AND receipt_id = %s",
            (rec["transaction_id"], receipt_id)
        )
        if not cur.fetchone():
            cur.execute(
                """
                INSERT INTO banking_receipt_matching_ledger (
                    banking_transaction_id, receipt_id, match_date, match_type, match_status, match_confidence, notes
                ) VALUES (
                    %s, %s, CURRENT_DATE, %s, %s, %s, %s
                )
                """,
                (rec["transaction_id"], receipt_id, "auto_fees", "linked", 0.99, "Auto-linked from export")
            )

        applied += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Applied receipts: {applied}")


if __name__ == "__main__":
    main()
