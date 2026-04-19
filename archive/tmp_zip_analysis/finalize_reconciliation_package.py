import csv
from collections import Counter
from pathlib import Path

BASE = Path(r"L:\limo\archive\tmp_zip_analysis")
CONFIRMED = BASE / "confirmed_entries_vs_receipts.csv"
CLASSIFIED = BASE / "receipts_cash_reimbursed_not_linked_classified.csv"

OUT_READY = BASE / "final_ready_to_apply_confirmed.csv"
OUT_MANUAL = BASE / "final_manual_exceptions_confirmed.csv"
OUT_CASH_PLAN = BASE / "final_cash_reimbursed_processing_plan.csv"
OUT_SUMMARY = BASE / "FINAL_RECONCILIATION_PACKAGE_SUMMARY.txt"


def to_int(v):
    try:
        return int(str(v).strip())
    except Exception:
        return 0


def load_confirmed():
    rows = []
    with open(CONFIRMED, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            ver = (row.get("verification") or "").strip()
            has_receipt = (row.get("receipt_exists") or "0") == "1"
            bank_id = (row.get("bank_txn_id") or "").strip()
            bank_link_cnt = to_int(row.get("bank_links_via_banking_table") or "0")

            action = ""
            reason = ""

            if ver in ("DIRECT_MATCH", "MERGED_MATCH") and (not has_receipt):
                action = "MANUAL_FIX_RECEIPT_LINK"
                reason = "bank matched but receipt missing"
            elif ver in ("DIRECT_MATCH", "MERGED_MATCH") and has_receipt and bank_link_cnt == 0:
                action = "MANUAL_VALIDATE_BANK_LINK"
                reason = "receipt exists but no bank->receipt pointer"
            elif ver in ("DIRECT_MATCH", "MERGED_MATCH") and bank_id:
                action = "APPLY_CONFIRMED"
                reason = "direct/merged bank evidence"
            elif ver == "RECEIPT_ONLY" and has_receipt:
                action = "APPLY_RECEIPT_ONLY"
                reason = "receipt evidence without bank linkage"
            else:
                action = "MANUAL_REVIEW"
                reason = "insufficient evidence"

            row["final_action"] = action
            row["final_reason"] = reason
            rows.append(row)
    return rows


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def build_cash_plan():
    rows = []
    with open(CLASSIFIED, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            bucket = row.get("classification_bucket", "")
            if bucket == "employee_reimbursement_likely":
                step = "post reimbursement or owner-draw mapping; no bank link expected"
                priority = 1
            elif bucket == "fuel_cash_likely":
                step = "batch post as fuel cash expenses; verify GST coding"
                priority = 2
            elif bucket == "vehicle_maintenance_cash_likely":
                step = "post to vehicle maintenance cash expenses"
                priority = 3
            elif bucket == "liquor_cash_likely":
                step = "review policy/tax treatment before posting"
                priority = 4
            else:
                step = "manual classify and post"
                priority = 5

            row["processing_priority"] = priority
            row["recommended_step"] = step
            rows.append(row)

    rows.sort(key=lambda x: (int(x.get("processing_priority", 9)), x.get("receipt_date", ""), x.get("receipt_id", "")))
    return rows


def main():
    confirmed = load_confirmed()

    ready = [r for r in confirmed if r.get("final_action") in ("APPLY_CONFIRMED", "APPLY_RECEIPT_ONLY")]
    manual = [r for r in confirmed if r.get("final_action") not in ("APPLY_CONFIRMED", "APPLY_RECEIPT_ONLY")]

    fields_confirmed = [
        "final_action", "final_reason",
        "source", "verification", "gl_date", "gl_chq", "gl_vendor", "gl_amount", "gl_account",
        "bank_txn_id", "bank_txn_date", "bank_debit", "bank_desc", "bank_check",
        "receipt_id", "receipt_exists", "receipt_date", "receipt_vendor", "receipt_amount",
        "receipt_payment_method", "bank_links_via_banking_table", "notes",
    ]

    write_csv(OUT_READY, ready, fields_confirmed)
    write_csv(OUT_MANUAL, manual, fields_confirmed)

    cash_plan = build_cash_plan()
    fields_cash = [
        "processing_priority", "recommended_step", "classification_bucket", "classification_reason",
        "receipt_id", "receipt_date", "vendor_name", "gross_amount",
        "payment_method", "canonical_pay_method", "is_driver_reimbursement", "reimbursed_via",
        "banking_transaction_id", "is_matched", "receipt_source",
    ]
    write_csv(OUT_CASH_PLAN, cash_plan, fields_cash)

    c_actions = Counter(r.get("final_action", "") for r in confirmed)
    c_buckets = Counter(r.get("classification_bucket", "") for r in cash_plan)

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("Final Reconciliation Package Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total confirmed rows: {len(confirmed)}\n")
        for k, v in c_actions.most_common():
            f.write(f"- {k}: {v}\n")
        f.write(f"\nReady-to-apply rows: {len(ready)}\n")
        f.write(f"Manual exception rows: {len(manual)}\n")
        f.write(f"\nCash/reimbursed plan rows: {len(cash_plan)}\n")
        for k, v in c_buckets.most_common():
            f.write(f"- {k}: {v}\n")

        # explicit note for known unresolved exception candidate
        f.write("\nKnown missing-receipt link candidate:\n")
        f.write("- 2012-12-03 CHQ 101 PARRS AUTOMOTIVE 2000.00 bank_txn_id=102510 likely receipt_id=140834\n")

    print(f"Total confirmed rows: {len(confirmed)}")
    print(f"Ready-to-apply rows: {len(ready)}")
    print(f"Manual exception rows: {len(manual)}")
    print(f"Cash/reimbursed plan rows: {len(cash_plan)}")
    print(f"Wrote: {OUT_READY}")
    print(f"Wrote: {OUT_MANUAL}")
    print(f"Wrote: {OUT_CASH_PLAN}")
    print(f"Wrote: {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
