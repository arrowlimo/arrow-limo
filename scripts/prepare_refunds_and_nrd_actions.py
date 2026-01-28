import argparse
import csv
import os
from decimal import Decimal
import psycopg2

CSV_PATH = r"L:\\limo\\reports\\CHARTERS_TO_REFUND.csv"
OUT_REFUND_ACTIONS = r"L:\\limo\\reports\\REFUND_ACTIONS_REVIEW.csv"
OUT_SQUARE_LOOKUP = r"L:\\limo\\reports\\SQUARE_LOOKUP_FOR_REFUNDS.csv"

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def load_candidates(path):
    items = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rn = (row.get("reserve_number") or row.get("Reserve") or "").strip()
            if not rn:
                continue
            refund_amt = row.get("refund_amount") or row.get("Refund") or row.get("refund") or "0"
            try:
                refund_amt = Decimal(str(refund_amt).replace(",", "").strip())
            except Exception:
                refund_amt = Decimal("0")
            items.append({"reserve_number": rn, "expected_refund": refund_amt})
    return items


def fetch_charter(cur, reserve_number):
    cur.execute(
        """
        SELECT charter_id, COALESCE(total_amount_due,0), COALESCE(paid_amount,0), COALESCE(balance,0),
               COALESCE(cancelled, FALSE)
        FROM charters WHERE reserve_number = %s
        """,
        (reserve_number,),
    )
    r = cur.fetchone()
    if not r:
        return None
    return {
        "charter_id": r[0],
        "total_amount_due": Decimal(str(r[1] or 0)),
        "paid_amount": Decimal(str(r[2] or 0)),
        "balance": Decimal(str(r[3] or 0)),
        "cancelled": bool(r[4]),
    }


def fetch_payments(cur, reserve_number):
    cur.execute(
        """
        SELECT payment_id, payment_date, COALESCE(amount,0), COALESCE(payment_method,''),
               COALESCE(reference_number,''), COALESCE(square_payment_id,''), COALESCE(square_status,''),
               COALESCE(notes,'')
        FROM payments
        WHERE reserve_number = %s
        ORDER BY payment_date, payment_id
        """,
        (reserve_number,),
    )
    rows = cur.fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "payment_id": r[0],
                "payment_date": r[1],
                "amount": Decimal(str(r[2] or 0)),
                "payment_method": r[3],
                "reference_number": r[4],
                "square_payment_id": r[5],
                "square_status": r[6],
                "notes": r[7],
            }
        )
    return out


def main():
    parser = argparse.ArgumentParser(description="Prepare refund vs NRD actions for refund candidates")
    args = parser.parse_args()

    candidates = load_candidates(CSV_PATH)
    conn = get_conn()
    try:
        cur = conn.cursor()

        actions = []
        square_rows = []
        for c in candidates:
            rn = c["reserve_number"]
            ch = fetch_charter(cur, rn)
            pays = fetch_payments(cur, rn)

            any_500 = any(p["amount"] == Decimal("500.00") for p in pays)
            charges_zero = (ch and ch["total_amount_due"] == 0)
            is_cancelled = bool(ch and ch["cancelled"]) 

            classification = "REFUND_DUE"
            reason = "Overpaid; refund expected"
            if is_cancelled and charges_zero and any_500:
                classification = "NRD_CANDIDATE"
                reason = "Cancelled + $0 charges + $500 payment"

            actions.append(
                {
                    "reserve_number": rn,
                    "charter_id": ch["charter_id"] if ch else "",
                    "cancelled": ch["cancelled"] if ch else "",
                    "status": "",
                    "category": "",
                    "total_amount_due": str(ch["total_amount_due"]) if ch else "",
                    "paid_amount": str(ch["paid_amount"]) if ch else "",
                    "balance": str(ch["balance"]) if ch else "",
                    "expected_refund": str(c["expected_refund"]),
                    "has_500_payment": any_500,
                    "payments_count": len(pays),
                    "classification": classification,
                    "reason": reason,
                }
            )

            for p in pays:
                square_rows.append(
                    {
                        "reserve_number": rn,
                        "payment_id": p["payment_id"],
                        "payment_date": p["payment_date"],
                        "amount": str(p["amount"]),
                        "payment_method": p["payment_method"],
                        "reference_number": p["reference_number"],
                        "square_payment_id": p["square_payment_id"],
                        "square_status": p["square_status"],
                        "notes": p["notes"],
                    }
                )

        # Write actions review
        with open(OUT_REFUND_ACTIONS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "reserve_number",
                    "charter_id",
                    "cancelled",
                    "status",
                    "category",
                    "total_amount_due",
                    "paid_amount",
                    "balance",
                    "expected_refund",
                    "has_500_payment",
                    "payments_count",
                    "classification",
                    "reason",
                ],
            )
            w.writeheader()
            for row in actions:
                w.writerow(row)

        # Write square lookup
        with open(OUT_SQUARE_LOOKUP, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "reserve_number",
                    "payment_id",
                    "payment_date",
                    "amount",
                    "payment_method",
                    "reference_number",
                    "square_payment_id",
                    "square_status",
                    "notes",
                ],
            )
            w.writeheader()
            for row in square_rows:
                w.writerow(row)

        print(f"Wrote {len(actions)} rows to {OUT_REFUND_ACTIONS}")
        print(f"Wrote {len(square_rows)} payment rows to {OUT_SQUARE_LOOKUP}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
