import csv
from pathlib import Path

import psycopg2

from _tmp_apply_fuzzy_driver_match_etransfers import (
    blocked_text,
    choose_employee,
    extract_candidate_name,
    load_email_name_aliases,
    load_employees,
)

OUT_CSV = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review.csv")
OUT_SUMMARY = Path(r"l:\limo\data\intake\etransfer_remaining_fuzzy_review_summary.csv")


def lane_for_row(description: str, candidate: str, best: float, second: float) -> str:
    d = (description or "").upper()
    c = (candidate or "").upper()

    if "DAVID RICHARD" in d or "DAVID RICHARD" in c or "KAREN RICHARD" in d or "KAREN RICHARD" in c:
        return "MANUAL_REVIEW"

    if any(k in d for k in ("HEFFNER", "INSURANCE", "AUTO SALES", "LEASING", "LEXUS")):
        return "VENDOR_REPAYMENT_REVIEW"

    if blocked_text(c):
        return "VENDOR_REPAYMENT_REVIEW"

    if best >= 0.82 and (best - second) >= 0.03:
        return "PERSON_REIMBURSEMENT_REVIEW"

    return "MANUAL_REVIEW"


def main():
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine"
    )
    cur = conn.cursor()

    employees = load_employees(cur)
    email_aliases_added = load_email_name_aliases(cur, employees)

    cur.execute(
        """
        SELECT transaction_id, transaction_date, debit_amount, description, vendor_extracted,
               COALESCE(reconciliation_status, '') AS reconciliation_status,
               COALESCE(is_transfer, false) AS is_transfer
        FROM banking_transactions
        WHERE debit_amount > 0
          AND receipt_id IS NULL
          AND reconciled_receipt_id IS NULL
          AND reconciled_payment_id IS NULL
          AND reconciled_charter_id IS NULL
          AND (
                description ILIKE '%e-transfer%'
                OR description ILIKE '%etransfer%'
                OR description ILIKE '%email transfer%'
              )
          AND reconciliation_status IS DISTINCT FROM 'DRIVER_PAY_FUZZY'
          AND reconciliation_status IS DISTINCT FROM 'CASH_BOX_REVIEW'
                    AND reconciliation_status IS DISTINCT FROM 'MANUAL_CLASSIFIED'
        ORDER BY transaction_date, transaction_id
        """
    )
    rows = cur.fetchall()

    review_rows = []
    summary = {}

    for tid, tdate, amt, desc, vendor, status, is_transfer in rows:
        extracted = extract_candidate_name(desc or "", vendor)
        if not extracted:
            extracted = ""

        emp, best, second = choose_employee(extracted, employees)
        lane = lane_for_row(desc or "", extracted, best, second)

        if lane not in summary:
            summary[lane] = {"count": 0, "amount": 0.0}
        summary[lane]["count"] += 1
        summary[lane]["amount"] += float(amt or 0)

        review_rows.append(
            {
                "transaction_id": tid,
                "transaction_date": str(tdate),
                "debit_amount": str(amt),
                "reconciliation_status": status,
                "is_transfer": "true" if is_transfer else "false",
                "description": desc or "",
                "vendor_extracted": vendor or "",
                "candidate_name": extracted,
                "best_employee_id": "" if emp is None else emp.employee_id,
                "best_employee_name": "" if emp is None else emp.display_name,
                "best_confidence": f"{best:.4f}",
                "second_confidence": f"{second:.4f}",
                "confidence_gap": f"{(best - second):.4f}",
                "recommended_lane": lane,
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "transaction_id",
                "transaction_date",
                "debit_amount",
                "reconciliation_status",
                "is_transfer",
                "description",
                "vendor_extracted",
                "candidate_name",
                "best_employee_id",
                "best_employee_name",
                "best_confidence",
                "second_confidence",
                "confidence_gap",
                "recommended_lane",
            ],
        )
        writer.writeheader()
        writer.writerows(review_rows)

    with OUT_SUMMARY.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["recommended_lane", "count", "amount"])
        for lane in sorted(summary.keys()):
            writer.writerow([lane, summary[lane]["count"], f"{summary[lane]['amount']:.2f}"])

    print(f"EMAIL_ALIASES_ADDED={email_aliases_added}")
    print(f"REMAINING_ROWS={len(review_rows)}")
    for lane in sorted(summary.keys()):
        print(f"{lane}|{summary[lane]['count']}|{summary[lane]['amount']:.2f}")
    print(f"DETAIL_CSV={OUT_CSV}")
    print(f"SUMMARY_CSV={OUT_SUMMARY}")

    # Show top rows that are close to threshold for quick manual action.
    likely = [r for r in review_rows if r["recommended_lane"] == "PERSON_REIMBURSEMENT_REVIEW"]
    likely.sort(key=lambda x: float(x["best_confidence"]), reverse=True)
    print("TOP_PERSON_REIMBURSEMENT_REVIEW")
    for r in likely[:20]:
        print(
            f"{r['transaction_id']}|{r['debit_amount']}|{r['candidate_name']}|"
            f"{r['best_employee_name']}|{r['best_confidence']}|{r['confidence_gap']}"
        )

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
