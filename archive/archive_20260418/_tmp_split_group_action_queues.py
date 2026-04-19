#!/usr/bin/env python3
"""
Split grouped unlinked debit backlog into:
- auto-safe queue
- manual-review queue
"""

from __future__ import annotations

import csv
from pathlib import Path

IN_CSV = Path(r"L:\limo\data\intake\unlinked_debits_group_samples.csv")
FULL_INPUT = Path(r"L:\limo\data\intake\missing_receipt_intake_queue.csv")
OUT_SAFE = Path(r"L:\limo\data\intake\unlinked_debits_auto_safe_queue.csv")
OUT_REVIEW = Path(r"L:\limo\data\intake\unlinked_debits_manual_review_queue.csv")

SAFE_GROUPS = {
    "LEASE_FINANCE",
    "INSURANCE",
    "TELECOM",
    "DRIVER_PAY_REIMBURSEMENT",
    "VEHICLE_MAINT",
    "FUEL",
}


def load_group_map() -> dict[int, str]:
    group_map: dict[int, str] = {}
    # Build a coarse map from samples; fallback routing uses text rules later.
    if IN_CSV.exists():
        with IN_CSV.open("r", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                tid = int(r["transaction_id"])
                group_map[tid] = r["group"]
    return group_map


def classify_text(vendor: str, desc: str) -> str:
    t = f"{vendor} {desc}".upper()
    if any(k in t for k in ("ARMOR HEATCO", "JASON ROGERS")):
        return "DRIVER_PAY_REIMBURSEMENT"
    if any(k in t for k in ("HEFFNER", "WOODRIDGE", "RIFCO", "LEASE", "AUTO FINANCE", "FORD CREDIT", "JACK CARTER")):
        return "LEASE_FINANCE"
    if any(k in t for k in ("TELUS", "ROGERS", "BELL", "SHAW", "PHONE", "MOBILE")):
        return "TELECOM"
    if any(k in t for k in ("INSURANCE", "ASI FINANCE", "ALL SERVICE INSURANCE", "FIRST INSURANCE")):
        return "INSURANCE"
    if any(k in t for k in ("KAL TIRE", "ERLES", "AUTO REPAIR", "MAINT", "PARTS", "REPAIR", "SERVICE")):
        return "VEHICLE_MAINT"
    if any(k in t for k in ("FAS GAS", "SHELL", "PETRO", "ESSO", "GAS", "FUEL")):
        return "FUEL"
    if any(k in t for k in ("LIQUOR", "PLENTY OF LIQUOR", "LIQUOR BARN")):
        return "LIQUOR"
    if any(k in t for k in ("ATM WITHDRAWAL", "ABM WITHDRAWAL", "CASH WITHDRAWAL", "BANK WITHDRAWAL", "WITHDRAWAL")):
        return "CASH_BOX_QUEUE"
    if any(k in t for k in ("E-TRANSFER", "ETRANSFER", "INTERAC E-TRANSFER", "TRANSFER")):
        return "TRANSFER_ETRANSFER"
    if any(k in t for k in ("NSF", "RETURN", "REVERSAL", "STOP")):
        return "NSF_REVERSAL"
    return "OTHER_REVIEW"


def main():
    group_map = load_group_map()

    safe_rows = []
    review_rows = []

    with FULL_INPUT.open("r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            tid = int(r["transaction_id"])
            g = group_map.get(tid) or classify_text(r.get("vendor_extracted", ""), r.get("description", ""))
            row = {
                "group": g,
                "transaction_id": r.get("transaction_id", ""),
                "transaction_date": r.get("transaction_date", ""),
                "description": r.get("description", ""),
                "debit_amount": r.get("debit_amount", ""),
                "category": r.get("category", ""),
                "vendor_extracted": r.get("vendor_extracted", ""),
            }
            if g in SAFE_GROUPS:
                safe_rows.append(row)
            else:
                review_rows.append(row)

    hdr = ["group", "transaction_id", "transaction_date", "description", "debit_amount", "category", "vendor_extracted"]

    with OUT_SAFE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerows(safe_rows)

    with OUT_REVIEW.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerows(review_rows)

    print("GROUP_SPLIT_DONE")
    print(f"safe_rows={len(safe_rows)}")
    print(f"review_rows={len(review_rows)}")
    print(f"safe_csv={OUT_SAFE}")
    print(f"review_csv={OUT_REVIEW}")


if __name__ == "__main__":
    main()
