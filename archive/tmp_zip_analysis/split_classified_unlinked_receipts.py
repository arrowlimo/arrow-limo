import csv
from collections import defaultdict
from pathlib import Path

IN_FILE = Path(r"L:\limo\archive\tmp_zip_analysis\receipts_cash_reimbursed_not_linked_classified.csv")
OUT_DIR = Path(r"L:\limo\archive\tmp_zip_analysis")


def safe_name(s):
    return s.lower().replace(" ", "_").replace("-", "_")


def main():
    buckets = defaultdict(list)
    with open(IN_FILE, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        fieldnames = r.fieldnames
        for row in r:
            buckets[row.get("classification_bucket", "manual_review_needed")].append(row)

    for bucket, rows in buckets.items():
        out = OUT_DIR / f"unlinked_receipts_{safe_name(bucket)}.csv"
        with open(out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"{bucket}: {len(rows)} -> {out}")


if __name__ == "__main__":
    main()
