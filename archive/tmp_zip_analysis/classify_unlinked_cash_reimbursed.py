import csv
from collections import Counter
from pathlib import Path

IN_FILE = Path(r"L:\limo\archive\tmp_zip_analysis\receipts_cash_reimbursed_not_linked_to_banking.csv")
OUT_CLASSIFIED = Path(r"L:\limo\archive\tmp_zip_analysis\receipts_cash_reimbursed_not_linked_classified.csv")
OUT_SUMMARY = Path(r"L:\limo\archive\tmp_zip_analysis\receipts_cash_reimbursed_not_linked_classified_summary.txt")

FUEL_KEYWORDS = {
    "CENTEX", "ESSO", "SHELL", "PETRO-CANADA", "FAS GAS", "MOHAWK", "HUSKY", "CHEVRON", "ULTRAMAR", "CO-OP"
}
LIQUOR_KEYWORDS = {"LIQUOR BARN", "LIQUOR DEPOT", "UPTOWN LIQUOR", "LIQUOR"}
OWNER_REIMB_KEYWORDS = {"REIMBURSE", "OWNER", "PERSONAL", "WITHDRAWAL", "UNLINKED EXPENSE REVIEW"}
MAINTENANCE_KEYWORDS = {
    "AUTO", "TIRE", "KAL-TIRE", "CARLINE", "MECHANICAL", "RADIATOR", "REPAIR", "GARAGE", "DETAIL"
}


def contains_any(text, keywords):
    t = (text or "").upper()
    return any(k in t for k in keywords)


def classify(row):
    vendor = (row.get("vendor_name") or "").upper()
    pay_method = (row.get("payment_method") or "").upper()
    canonical = (row.get("canonical_pay_method") or "").upper()
    reimb = (row.get("reimbursed_via") or "").upper()
    source = (row.get("receipt_source") or "").upper()
    is_driver_reimb = (row.get("is_driver_reimbursement") or "").strip().lower() == "true"

    # Priority order: explicit reimbursement flags first
    if "REIMB" in pay_method or "REIMB" in canonical or is_driver_reimb or reimb:
        if contains_any(vendor + " " + source, OWNER_REIMB_KEYWORDS):
            return "owner_reimbursement_likely", "reimbursement flag + owner/personal keyword"
        return "employee_reimbursement_likely", "reimbursement flag"

    if contains_any(vendor, FUEL_KEYWORDS):
        return "fuel_cash_likely", "fuel vendor keyword"

    if contains_any(vendor, LIQUOR_KEYWORDS):
        return "liquor_cash_likely", "liquor vendor keyword"

    if contains_any(vendor, MAINTENANCE_KEYWORDS):
        return "vehicle_maintenance_cash_likely", "maintenance vendor keyword"

    if "CASH" in pay_method or "CASH" in canonical:
        return "petty_cash_business_likely", "cash method with non-specific vendor"

    return "manual_review_needed", "no high-confidence pattern"


def main():
    rows = []
    with open(IN_FILE, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            bucket, reason = classify(row)
            row["classification_bucket"] = bucket
            row["classification_reason"] = reason
            rows.append(row)

    # Write classified output
    fieldnames = list(rows[0].keys()) if rows else []
    with open(OUT_CLASSIFIED, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # Build summary
    bucket_counts = Counter(r["classification_bucket"] for r in rows)
    vendor_counts = Counter((r.get("vendor_name") or "").strip() for r in rows)

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("Unlinked Cash/Reimbursed Receipts - Classification Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total rows: {len(rows)}\n\n")
        f.write("By bucket:\n")
        for k, v in bucket_counts.most_common():
            f.write(f"- {k}: {v}\n")
        f.write("\nTop 20 vendors:\n")
        for vname, n in vendor_counts.most_common(20):
            f.write(f"- {vname}: {n}\n")

    print(f"Total rows: {len(rows)}")
    print("Buckets:")
    for k, v in bucket_counts.most_common():
        print(f"  {k}: {v}")
    print(f"Wrote: {OUT_CLASSIFIED}")
    print(f"Wrote: {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
