#!/usr/bin/env python3
"""
Build first-pass cash-box decision sheet from manual review queue.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

IN_CSV = Path(r"L:\limo\data\intake\unlinked_debits_manual_review_queue.csv")
OUT_DIR = Path(r"L:\limo\data\intake")
OUT_DETAIL = OUT_DIR / "cash_box_queue_decision_sheet.csv"
OUT_SUMMARY = OUT_DIR / "cash_box_queue_decision_summary.csv"


def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def recommend_action(desc: str, vendor: str) -> tuple[str, str, str]:
    t = f"{vendor} {desc}".upper()

    # High-confidence reimbursement signals
    if any(k in t for k in ("DRIVER", "REIMBURSE", "PAYROLL REIMBURSEMENT", "ARMOR HEATCO", "JASON ROGERS")):
        return ("REIMBURSEMENT", "5260", "driver_or_reimbursement_signal")

    # Cash movement that should stay in cash-box lane
    if any(k in t for k in ("WITHDRAWAL", "ATM", "ABM", "CASH WITHDRAWAL", "BANK WITHDRAWAL", "BRANCH TRANSACTION WITHDRAWAL")):
        return ("CASH_BOX_MOVEMENT", "2270", "withdrawal_cash_movement")

    # Transfer style movements
    if any(k in t for k in ("E-TRANSFER", "ETRANSFER", "INTERAC E-TRANSFER", "TRANSFER")):
        return ("TRANSFER_REVIEW", "1099", "transfer_movement")

    # Known business purchases paid from cash box
    if any(k in t for k in ("LIQUOR", "LIQUOR BARN", "PLENTY OF LIQUOR")):
        return ("BUSINESS_PURCHASE", "5720", "liquor_purchase")

    return ("MANUAL_REVIEW", "", "insufficient_signal")


def main():
    if not IN_CSV.exists():
        raise SystemExit(f"Missing file: {IN_CSV}")

    rows = list(csv.DictReader(open(IN_CSV, "r", encoding="utf-8")))

    details = []
    by_action_count = defaultdict(int)
    by_action_amt = defaultdict(lambda: Decimal("0"))

    for r in rows:
        if (r.get("group") or "") != "CASH_BOX_QUEUE":
            continue

        action, gl, rule = recommend_action(r.get("description", ""), r.get("vendor_extracted", ""))
        amt = to_decimal(r.get("debit_amount", 0))

        details.append([
            r.get("transaction_id", ""),
            r.get("transaction_date", ""),
            r.get("debit_amount", ""),
            r.get("vendor_extracted", ""),
            r.get("description", ""),
            r.get("category", ""),
            action,
            gl,
            rule,
        ])

        by_action_count[action] += 1
        by_action_amt[action] += amt

    with OUT_DETAIL.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "transaction_id",
            "transaction_date",
            "debit_amount",
            "vendor_extracted",
            "description",
            "banking_category",
            "recommended_action",
            "suggested_gl",
            "rule",
        ])
        w.writerows(details)

    ordered_actions = sorted(by_action_count.keys(), key=lambda k: by_action_amt[k], reverse=True)
    with OUT_SUMMARY.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["recommended_action", "row_count", "amount_total"])
        for a in ordered_actions:
            w.writerow([a, by_action_count[a], float(by_action_amt[a])])

    print("CASHBOX_DECISION_SHEET_DONE")
    print(f"input_rows={len(rows)}")
    print(f"cash_box_rows={len(details)}")
    print(f"detail_csv={OUT_DETAIL}")
    print(f"summary_csv={OUT_SUMMARY}")
    print("TOP_ACTIONS")
    for a in ordered_actions[:8]:
        print(f"{a}|{by_action_count[a]}|{by_action_amt[a]}")


if __name__ == "__main__":
    main()
