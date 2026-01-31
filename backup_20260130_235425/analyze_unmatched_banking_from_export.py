#!/usr/bin/env python3
"""
Analyze unmatched banking transactions from a full JSON export of almsdata.

Inputs:
- reports/complete_almsdata_export.json (or .json.gz)

Outputs (in reports/):
- unmatched_banking_from_export.csv  (one row per unmatched banking transaction)
- reconciliation_actions_banking.md  (summary + action plan)

Rules and context:
- A banking transaction is considered "linked" if a row exists in receipts
  with receipts.bank_id = banking_transactions.transaction_id.
- All other banking rows are considered unmatched for the purposes of this report.
- We attempt light classification by description to propose CRA-compliant actions:
  • bank_fees: create a receipt with is_taxable=false (GST/HST typically not applicable)
  • nsf/chargeback: create a receipt with is_taxable=false; also look for reversal pairs
  • interest: create a receipt with is_taxable=false
  • cash_withdrawal/ATM: flag as needs driver receipt or petty-cash reconciliation
  • e_transfer: likely revenue/customer payment; verify linkage to payments/clients
  • merchant_deposit (Square/Moneris/Global): likely revenue; verify payment linkage
  • credit_card_payment: transfer to credit card account (not an expense receipt)
  • internal_transfer: transfer between accounts (no receipt)
  • unknown: needs review

Notes:
- This script reads from the JSON export only; it does not touch the database.
- It uses simple heuristics; it does not perform fuzzy matching to payments.
"""

import argparse
import csv
import gzip
import io
import json
import os
import re
from datetime import datetime


REPORTS_DIR = os.path.join("reports")
DEFAULT_EXPORT_JSON = os.path.join(REPORTS_DIR, "complete_almsdata_export.json")


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


def normalize_desc(desc: str) -> str:
    return (desc or "").strip()


def classify_banking_row(description: str, debit: float, credit: float) -> str:
    d = (description or "").lower()
    # Common patterns
    if any(k in d for k in ["nsf", "non-sufficient", "returned item", "chargeback", "reversal fee"]):
        return "nsf_or_chargeback"
    if any(k in d for k in ["service charge", "bank fee", "monthly fee", "plan fee", "svc chg", "fee "]):
        return "bank_fee"
    if any(k in d for k in ["interest", "int chg", "overdraft interest"]):
        return "interest"
    if any(k in d for k in ["interac", "e-transfer", "etransfer", "e transfer", "e- transfer"]):
        return "e_transfer"
    if any(k in d for k in ["square", "global payments", "moneris", "pos deposit", "merchant deposit"]):
        return "merchant_deposit"
    if any(k in d for k in ["atm", "abm", "cash withdrawal", "cashwd", "cash wd", "cash w/d"]):
        return "cash_withdrawal"
    if any(k in d for k in ["visa payment", "mastercard payment", "mc payment", "card payment", "credit card payment"]):
        return "credit_card_payment"
    if any(k in d for k in ["transfer", "xfer", "x-fer", "to savings", "from chequing", "between accounts"]):
        return "internal_transfer"
    if any(k in d for k in ["deposit", "credit "]):
        # generic deposit; keep separate from merchant/e-transfer where possible
        return "deposit"
    if any(k in d for k in ["debit", "withdrawal", "payment"]):
        return "debit_generic"
    return "unknown"


def ocr_suspicious(description: str) -> bool:
    if not description:
        return False
    d = description
    # Flag non-ASCII or obvious OCR swap characters clustered together
    if any(ord(ch) > 126 for ch in d):
        return True
    # Common OCR confusions: O/0, I/1, S/5, B/8
    if re.search(r"[O0]{3,}|[I1]{3,}|[S5]{3,}|[B8]{3,}", d):
        return True
    # Highlighter bleed often produces runs of = or unusual punctuation
    if re.search(r"={3,}|\*{3,}|~{3,}", d):
        return True
    return False


def table_to_dicts(table_node):
    """Convert an export table node with columns/rows into list of dicts."""
    if isinstance(table_node, list):
        # Already list of dicts
        return table_node
    if isinstance(table_node, dict):
        cols = table_node.get("columns")
        rows = table_node.get("rows")
        if isinstance(cols, list) and isinstance(rows, list):
            out = []
            for r in rows:
                if isinstance(r, (list, tuple)):
                    d = {cols[i]: r[i] if i < len(r) else None for i in range(len(cols))}
                    out.append(d)
                elif isinstance(r, dict):
                    out.append(r)
            return out
    return []


def main():
    parser = argparse.ArgumentParser(description="Analyze unmatched banking from export JSON")
    parser.add_argument("--export", default=DEFAULT_EXPORT_JSON,
                        help="Path to complete_almsdata_export.json or .json.gz")
    parser.add_argument("--out-csv", default=os.path.join(REPORTS_DIR, "unmatched_banking_from_export.csv"),
                        help="Output CSV path")
    parser.add_argument("--out-md", default=os.path.join(REPORTS_DIR, "reconciliation_actions_banking.md"),
                        help="Output Markdown summary path")
    args = parser.parse_args()

    data = load_export(args.export)

    # Support both flat and nested (tables={...}) export structures
    table_root = data.get("tables") if isinstance(data, dict) and "tables" in data else data
    if not isinstance(table_root, dict):
        table_root = {}

    banking = table_to_dicts(table_root.get("banking_transactions"))
    receipts = table_to_dicts(table_root.get("receipts"))
    receipt_match_ledger = table_to_dicts(table_root.get("banking_receipt_matching_ledger"))
    banking_payment_links = table_to_dicts(table_root.get("banking_payment_links"))

    # Build index of bank ids linked to receipts (via matching ledger) and to payments
    used_bank_ids_receipts = set()
    for m in receipt_match_ledger:
        bid = m.get("banking_transaction_id")
        rid = m.get("receipt_id")
        if bid is not None and rid is not None:
            used_bank_ids_receipts.add(bid)

    used_bank_ids_payments = set()
    for l in banking_payment_links:
        bid = l.get("banking_transaction_id")
        pid = l.get("payment_id")
        if bid is not None and pid is not None:
            used_bank_ids_payments.add(bid)

    unmatched = []
    counters = {
        "total_bank_rows": 0,
        "linked_via_receipt": 0,
        "linked_via_payment": 0,
        "unmatched": 0,
    }
    class_counts = {}
    ocr_flags = 0

    for row in banking:
        counters["total_bank_rows"] += 1
        tid = row.get("transaction_id")
        desc = normalize_desc(row.get("description"))
        debit = float(row.get("debit_amount") or 0)
        credit = float(row.get("credit_amount") or 0)
        date = row.get("transaction_date")
        acct = row.get("account_number") or ""

        if tid in used_bank_ids_receipts:
            counters["linked_via_receipt"] += 1
            continue
        if tid in used_bank_ids_payments:
            counters["linked_via_payment"] += 1
            continue

        label = classify_banking_row(desc, debit, credit)
        class_counts[label] = class_counts.get(label, 0) + 1
        suspicious = ocr_suspicious(desc)
        if suspicious:
            ocr_flags += 1

        recommended_action = "review"
        tax_note = ""

        # Recommended actions based on classification
        if label in ("bank_fee", "nsf_or_chargeback", "interest"):
            recommended_action = "create_receipt"
            tax_note = "is_taxable=false; gst_amount=0"
        elif label == "cash_withdrawal":
            recommended_action = "petty_cash_reconcile_or_driver_receipt"
        elif label in ("e_transfer", "merchant_deposit", "deposit"):
            recommended_action = "verify_revenue_linkage"
        elif label == "credit_card_payment":
            recommended_action = "record_transfer_to_cc_account"
        elif label == "internal_transfer":
            recommended_action = "record_internal_transfer"
        else:
            recommended_action = "review"

        unmatched.append({
            "transaction_id": tid,
            "transaction_date": date,
            "account_number": acct,
            "description": desc,
            "debit_amount": debit,
            "credit_amount": credit,
            "classification": label,
            "ocr_suspicious": suspicious,
            "recommended_action": recommended_action,
            "tax_note": tax_note,
        })

    counters["unmatched"] = len(unmatched)

    # Ensure reports directory exists
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Write CSV
    fieldnames = [
        "transaction_id","transaction_date","account_number","description",
        "debit_amount","credit_amount","classification","ocr_suspicious",
        "recommended_action","tax_note",
    ]
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in unmatched:
            w.writerow(row)

    # Write Markdown summary with counts and guidance
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"# Banking Reconciliation - Unmatched Summary\n")
    lines.append(f"Generated: {now}\n")
    lines.append("")
    lines.append("## Totals")
    lines.append(f"- Total banking rows: {counters['total_bank_rows']}")
    lines.append(f"- Linked via receipts: {counters['linked_via_receipt']}")
    lines.append(f"- Linked via payments: {counters['linked_via_payment']}")
    lines.append(f"- Unmatched banking rows: {counters['unmatched']}")
    lines.append(f"- OCR-suspicious descriptions: {ocr_flags}")
    lines.append("")
    lines.append("## Classification Counts")
    for k in sorted(class_counts.keys()):
        lines.append(f"- {k}: {class_counts[k]}")
    lines.append("")
    lines.append("## Recommended Actions")
    lines.append("- bank_fee / nsf_or_chargeback / interest: create receipt with is_taxable=false (GST/HST 0)")
    lines.append("- cash_withdrawal: reconcile via petty cash log or attach driver receipt")
    lines.append("- e_transfer / merchant_deposit / deposit: verify revenue linkage (payments/clients)")
    lines.append("- credit_card_payment: record transfer to the corresponding credit card account")
    lines.append("- internal_transfer: record inter-account transfer, no receipt")
    lines.append("- unknown: review and classify; consider creating receipt if expense")
    lines.append("")
    lines.append("## OCR Review Cues")
    lines.append("Flagged descriptions may contain highlighter/scan artifacts; verify against statement images.")
    lines.append("")
    lines.append("## Output Files")
    lines.append(f"- CSV: `{os.path.relpath(args.out_csv)}`")
    lines.append(f"- Summary: `{os.path.relpath(args.out_md)}`")

    with open(args.out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✓ Wrote {args.out_csv}")
    print(f"✓ Wrote {args.out_md}")


if __name__ == "__main__":
    main()
