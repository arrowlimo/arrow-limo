import csv
import os
import psycopg2
from decimal import Decimal

CSV_PATH = r"L:\\limo\\reports\\CHARTERS_TO_REFUND.csv"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def load_candidates(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            res = (row.get("reserve_number") or row.get("Reserve") or "").strip()
            if not res:
                continue
            refund_amt = row.get("refund_amount") or row.get("Refund") or row.get("refund") or "0"
            try:
                refund_amt = Decimal(str(refund_amt).replace(",", "").strip())
            except Exception:
                refund_amt = Decimal("0")
            rows.append({"reserve_number": res, "expected_refund": refund_amt})
    return rows


def main():
    candidates = load_candidates(CSV_PATH)
    print(f"Analyzing {len(candidates)} refund candidates in charter_refunds...")
    found = 0
    total_found_amt = Decimal("0")

    conn = get_conn()
    try:
        cur = conn.cursor()
        for c in candidates:
            rn = c["reserve_number"]
            cur.execute(
                """
                SELECT COALESCE(SUM(amount),0), COUNT(*)
                FROM charter_refunds
                WHERE reserve_number = %s OR charter_id::text = %s
                """,
                (rn, rn),
            )
            amt, cnt = cur.fetchone()
            amt = Decimal(str(amt or 0))
            if cnt and amt != 0:
                print(f"  {rn}: {cnt} refund rows totalling {amt}")
                found += 1
                total_found_amt += amt
            else:
                print(f"  {rn}: no rows in charter_refunds")
        print(f"\nSummary: {found} of {len(candidates)} have entries in charter_refunds totalling {total_found_amt}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
