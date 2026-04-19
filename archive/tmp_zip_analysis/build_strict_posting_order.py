import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

IN_FILE = Path(r"L:\limo\archive\tmp_zip_analysis\final_cash_reimbursed_processing_plan.csv")
OUT_ORDER = Path(r"L:\limo\archive\tmp_zip_analysis\strict_posting_order.csv")
OUT_QUEUE = Path(r"L:\limo\archive\tmp_zip_analysis\strict_posting_order_queue_by_bucket.csv")
OUT_VENDOR = Path(r"L:\limo\archive\tmp_zip_analysis\strict_posting_order_vendor_batches.csv")
OUT_SUMMARY = Path(r"L:\limo\archive\tmp_zip_analysis\strict_posting_order_summary.txt")


def parse_date(s):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def safe_int(v, default=9):
    try:
        return int(str(v).strip())
    except Exception:
        return default


def target_from_bucket(bucket):
    b = (bucket or "").strip()
    if b == "employee_reimbursement_likely":
        return "liability_reimbursement_queue"
    if b == "fuel_cash_likely":
        return "expense_fuel_cash_queue"
    if b == "vehicle_maintenance_cash_likely":
        return "expense_vehicle_maintenance_cash_queue"
    if b == "liquor_cash_likely":
        return "policy_review_liquor_cash_queue"
    if b == "petty_cash_business_likely":
        return "expense_petty_cash_queue"
    return "manual_review_queue"


def load_rows():
    rows = []
    with open(IN_FILE, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            pr = safe_int(row.get("processing_priority"), 9)
            d = parse_date(row.get("receipt_date"))
            vendor = (row.get("vendor_name") or "").strip()
            bucket = (row.get("classification_bucket") or "manual_review_needed").strip()
            amt = (row.get("gross_amount") or "").strip()

            row["processing_priority"] = pr
            row["parsed_date"] = d
            row["vendor_name"] = vendor
            row["classification_bucket"] = bucket
            row["gl_target_hint"] = target_from_bucket(bucket)
            row["month_key"] = d.strftime("%Y-%m") if d else "unknown"
            row["gross_amount"] = amt
            rows.append(row)
    return rows


def write_csv(path, rows, fields):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            out = {}
            for k in fields:
                val = r.get(k, "")
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                out[k] = val
            w.writerow(out)


def main():
    rows = load_rows()

    # Strict processing order
    rows_sorted = sorted(
        rows,
        key=lambda x: (
            x["processing_priority"],
            x["parsed_date"] or datetime.min.date(),
            x["classification_bucket"],
            x["vendor_name"],
            x.get("receipt_id") or "",
        ),
    )

    for i, r in enumerate(rows_sorted, 1):
        r["strict_order"] = i
        r["batch_id"] = f"P{r['processing_priority']}-{r['month_key']}-{r['classification_bucket']}"

    fields = [
        "strict_order",
        "batch_id",
        "processing_priority",
        "classification_bucket",
        "gl_target_hint",
        "receipt_id",
        "receipt_date",
        "vendor_name",
        "gross_amount",
        "payment_method",
        "canonical_pay_method",
        "is_driver_reimbursement",
        "reimbursed_via",
        "recommended_step",
        "receipt_source",
    ]
    write_csv(OUT_ORDER, rows_sorted, fields)

    # Queue by bucket summary
    queue = defaultdict(lambda: {"count": 0, "amount": 0.0})
    for r in rows_sorted:
        k = (r["processing_priority"], r["classification_bucket"], r["gl_target_hint"], r["recommended_step"])
        queue[k]["count"] += 1
        try:
            queue[k]["amount"] += float(r.get("gross_amount") or 0)
        except Exception:
            pass

    queue_rows = []
    for (p, b, g, step), v in sorted(queue.items(), key=lambda x: (x[0][0], x[0][1])):
        queue_rows.append(
            {
                "processing_priority": p,
                "classification_bucket": b,
                "gl_target_hint": g,
                "recommended_step": step,
                "row_count": v["count"],
                "total_amount": f"{v['amount']:.2f}",
            }
        )

    write_csv(
        OUT_QUEUE,
        queue_rows,
        [
            "processing_priority",
            "classification_bucket",
            "gl_target_hint",
            "recommended_step",
            "row_count",
            "total_amount",
        ],
    )

    # Vendor batch summary within each priority
    vendor = defaultdict(lambda: {"count": 0, "amount": 0.0, "first_date": None, "last_date": None})
    for r in rows_sorted:
        k = (r["processing_priority"], r["classification_bucket"], r["vendor_name"])
        vendor[k]["count"] += 1
        try:
            vendor[k]["amount"] += float(r.get("gross_amount") or 0)
        except Exception:
            pass
        d = r["parsed_date"]
        if d:
            if vendor[k]["first_date"] is None or d < vendor[k]["first_date"]:
                vendor[k]["first_date"] = d
            if vendor[k]["last_date"] is None or d > vendor[k]["last_date"]:
                vendor[k]["last_date"] = d

    vendor_rows = []
    for (p, b, vname), st in sorted(vendor.items(), key=lambda x: (x[0][0], -x[1]["count"], x[0][2])):
        vendor_rows.append(
            {
                "processing_priority": p,
                "classification_bucket": b,
                "vendor_name": vname,
                "row_count": st["count"],
                "total_amount": f"{st['amount']:.2f}",
                "first_date": st["first_date"].isoformat() if st["first_date"] else "",
                "last_date": st["last_date"].isoformat() if st["last_date"] else "",
            }
        )

    write_csv(
        OUT_VENDOR,
        vendor_rows,
        [
            "processing_priority",
            "classification_bucket",
            "vendor_name",
            "row_count",
            "total_amount",
            "first_date",
            "last_date",
        ],
    )

    cnt_bucket = Counter(r["classification_bucket"] for r in rows_sorted)
    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("Strict Posting Order Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total rows: {len(rows_sorted)}\n")
        f.write("By bucket:\n")
        for k, v in cnt_bucket.most_common():
            f.write(f"- {k}: {v}\n")
        f.write("\nFiles:\n")
        f.write(f"- {OUT_ORDER}\n")
        f.write(f"- {OUT_QUEUE}\n")
        f.write(f"- {OUT_VENDOR}\n")

    print(f"Total rows: {len(rows_sorted)}")
    print(f"Wrote: {OUT_ORDER}")
    print(f"Wrote: {OUT_QUEUE}")
    print(f"Wrote: {OUT_VENDOR}")
    print(f"Wrote: {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
