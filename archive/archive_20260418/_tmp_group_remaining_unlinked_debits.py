#!/usr/bin/env python3
"""
Group remaining unlinked debit transactions into actionable buckets and export samples.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

OUT_DIR = Path(r"L:\limo\data\intake")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SUMMARY_CSV = OUT_DIR / "unlinked_debits_group_summary.csv"
SAMPLES_CSV = OUT_DIR / "unlinked_debits_group_samples.csv"


def to_decimal(v: object) -> Decimal:
    if v is None:
        return Decimal("0")
    return Decimal(str(v))


def classify_group(vendor: str, desc: str) -> str:
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
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute(
        """
        SELECT
            transaction_id,
            transaction_date,
            COALESCE(vendor_extracted,'') AS vendor_extracted,
            COALESCE(description,'') AS description,
            COALESCE(category,'') AS category,
            COALESCE(debit_amount,0) AS debit_amount
        FROM banking_transactions
        WHERE COALESCE(debit_amount,0) > 0
          AND receipt_id IS NULL
        ORDER BY debit_amount DESC, transaction_date
        """
    )
    rows = cur.fetchall()

    grouped_counts: dict[str, int] = defaultdict(int)
    grouped_amounts: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    grouped_samples: dict[str, list[dict]] = defaultdict(list)

    for r in rows:
        g = classify_group(r["vendor_extracted"], r["description"])
        amt = to_decimal(r["debit_amount"])
        grouped_counts[g] += 1
        grouped_amounts[g] += amt
        if len(grouped_samples[g]) < 8:
            grouped_samples[g].append(r)

    ordered = sorted(grouped_counts.keys(), key=lambda k: grouped_amounts[k], reverse=True)

    with SUMMARY_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "transaction_count", "debit_amount_total"])
        for g in ordered:
            w.writerow([g, grouped_counts[g], float(grouped_amounts[g])])

    with SAMPLES_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "group",
            "transaction_id",
            "transaction_date",
            "vendor_extracted",
            "description",
            "category",
            "debit_amount",
        ])
        for g in ordered:
            for r in grouped_samples[g]:
                w.writerow([
                    g,
                    r["transaction_id"],
                    r["transaction_date"],
                    r["vendor_extracted"],
                    r["description"],
                    r["category"],
                    float(to_decimal(r["debit_amount"])),
                ])

    print("UNLINKED_GROUPING_DONE")
    print(f"rows={len(rows)}")
    print(f"groups={len(ordered)}")
    print(f"summary_csv={SUMMARY_CSV}")
    print(f"samples_csv={SAMPLES_CSV}")

    print("TOP_GROUPS")
    for g in ordered[:10]:
        print(f"{g}|{grouped_counts[g]}|{grouped_amounts[g]}")

    print("SAMPLE_LINES")
    shown = 0
    for g in ordered[:4]:
        for r in grouped_samples[g][:3]:
            print(
                f"{g}|{r['transaction_id']}|{r['transaction_date']}|"
                f"{to_decimal(r['debit_amount'])}|{(r['vendor_extracted'] or '')[:40]}|"
                f"{(r['description'] or '')[:60]}"
            )
            shown += 1
            if shown >= 12:
                break
        if shown >= 12:
            break

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
