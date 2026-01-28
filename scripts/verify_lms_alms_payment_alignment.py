import os
import csv
import psycopg2
try:
    import pyodbc
except ImportError:
    pyodbc = None

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

OUT_SUMMARY = r"L:\\limo\\reports\\LMS_ALMS_PAYMENT_ALIGNMENT_SUMMARY.csv"
OUT_MISMATCH = r"L:\\limo\\reports\\LMS_ALMS_PAYMENT_MISMATCHES.csv"
OUT_RESERVE = r"L:\\limo\\reports\\LMS_ALMS_RESERVE_TOTALS.csv"


def fetch_lms():
    if pyodbc is None:
        raise RuntimeError("pyodbc is required to read LMS .mdb; please install it.")
    path = r"L:\\limo\\backups\\lms.mdb"
    conn = pyodbc.connect(rf'Driver={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={path};')
    cur = conn.cursor()
    cur.execute("SELECT PaymentID, Reserve_No, Amount, LastUpdated FROM Payment ORDER BY PaymentID")
    rows = []
    for r in cur.fetchall():
        rows.append({
            "payment_id": str(r[0]).strip() if r[0] is not None else "",
            "reserve_number": str(r[1]).strip() if r[1] is not None else "",
            "amount": float(r[2] or 0),
            "payment_date": r[3],
        })
    cur.close()
    conn.close()
    return rows


def fetch_alms():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT reserve_number, amount, reference_number, payment_date
        FROM payments
        ORDER BY payment_id
        """
    )
    rows = []
    for r in cur.fetchall():
        rows.append({
            "reserve_number": r[0] or "",
            "amount": float(r[1] or 0),
            "reference_number": r[2] or "",
            "payment_date": r[3],
        })
    cur.close()
    conn.close()
    return rows


def main():
    lms = fetch_lms()
    alms = fetch_alms()

    # Map ALMS by LMS PaymentID using reference_number=LMS-Payment-<id>
    alms_by_pid = {}
    for a in alms:
        ref = a.get("reference_number") or ""
        if ref.startswith("LMS-Payment-"):
            pid = ref.replace("LMS-Payment-", "").strip()
            # If multiple rows share same ref (split), sum them
            prev = alms_by_pid.get(pid)
            if prev:
                prev["amount"] += a["amount"]
            else:
                alms_by_pid[pid] = {"amount": a["amount"], "reserve_number": a["reserve_number"], "count": 1}
        else:
            # Non-LMS references ignored for PID matching
            pass

    mismatches = []
    for r in lms:
        pid = r["payment_id"]
        lms_amt = r["amount"]
        alms_rec = alms_by_pid.get(pid)
        alms_amt = alms_rec["amount"] if alms_rec else 0.0
        if abs((alms_amt or 0.0) - (lms_amt or 0.0)) > 0.009:
            mismatches.append({
                "payment_id": pid,
                "reserve_number": r["reserve_number"],
                "lms_amount": lms_amt,
                "alms_amount": alms_amt,
                "diff": round(alms_amt - lms_amt, 2),
            })

    # Per-reserve totals
    lms_by_res = {}
    for r in lms:
        rn = r["reserve_number"] or ""
        lms_by_res[rn] = lms_by_res.get(rn, 0.0) + r["amount"]
    alms_by_res = {}
    for a in alms:
        rn = a["reserve_number"] or ""
        alms_by_res[rn] = alms_by_res.get(rn, 0.0) + a["amount"]

    # Write reports
    os.makedirs(os.path.dirname(OUT_SUMMARY), exist_ok=True)
    with open(OUT_SUMMARY, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["total_lms", "total_alms", "lms_payments", "alms_rows", "mismatches"])
        w.writeheader()
        w.writerow({
            "total_lms": sum(r["amount"] for r in lms),
            "total_alms": sum(a["amount"] for a in alms),
            "lms_payments": len(lms),
            "alms_rows": len(alms),
            "mismatches": len(mismatches),
        })

    with open(OUT_MISMATCH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["payment_id", "reserve_number", "lms_amount", "alms_amount", "diff"])
        w.writeheader()
        for m in mismatches:
            w.writerow(m)

    with open(OUT_RESERVE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["reserve_number", "lms_total", "alms_total", "diff"])
        w.writeheader()
        reserves = set(list(lms_by_res.keys()) + list(alms_by_res.keys()))
        for rn in sorted(reserves):
            l = lms_by_res.get(rn, 0.0)
            a = alms_by_res.get(rn, 0.0)
            w.writerow({
                "reserve_number": rn,
                "lms_total": l,
                "alms_total": a,
                "diff": round(a - l, 2),
            })

    print("Alignment summary written:", OUT_SUMMARY)
    print("Mismatches written:", OUT_MISMATCH, "count=", len(mismatches))
    print("Per-reserve totals written:", OUT_RESERVE)


if __name__ == "__main__":
    main()
