import os
import csv
import psycopg2


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        dbname=os.getenv("DB_NAME", "almsdata"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "ArrowLimousine"),
    )


def load_refund_candidates(csv_path):
    reserves = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                ra = float(row["refund_amount"] or 0)
            except Exception:
                ra = 0.0
            reserves.append((row["reserve_number"], ra))
    # de-dup while preserving order
    seen = set()
    uniq = []
    for r in reserves:
        if r[0] not in seen:
            uniq.append(r)
            seen.add(r[0])
    return uniq


def main():
    csv_path = r"L:\limo\reports\CHARTERS_TO_REFUND.csv"
    if not os.path.exists(csv_path):
        print(f"CSV not found: {csv_path}")
        return 1

    reserves = load_refund_candidates(csv_path)
    print(f"Analyzing {len(reserves)} refund candidates for existing refunds/negative payments...\n")

    sql = (
        "SELECT payment_id, reserve_number, amount, COALESCE(payment_method,''), "
        "payment_date, COALESCE(reference_number,''), COALESCE(payment_key,''), "
        "COALESCE(square_payment_id,''), COALESCE(square_status,''), COALESCE(notes,'') "
        "FROM payments WHERE reserve_number = %s ORDER BY payment_date, payment_id"
    )

    with get_conn() as conn:
        with conn.cursor() as cur:
            found = []
            for rn, exp_refund in reserves:
                cur.execute(sql, (rn,))
                rows = cur.fetchall()
                neg = [
                    r
                    for r in rows
                    if (r[2] is not None and float(r[2]) < 0)
                    or (r[3] and "refund" in r[3].lower())
                    or (r[8] and "refund" in r[8].lower())
                    or (r[9] and "refund" in r[9].lower())
                ]
                if neg:
                    total_neg = sum(abs(float(r[2] or 0)) for r in neg)
                    found.append((rn, exp_refund, total_neg, len(neg)))
                    print(
                        f"{rn}: FOUND existing refund-like payments count={len(neg)} total=${total_neg:,.2f} (expected ${exp_refund:,.2f})"
                    )
                    for r in neg[:5]:
                        print(
                            f"  pay_id={r[0]} amt={r[2]} date={r[4]} method={r[3]} square_id={r[7]} status={r[8]} ref={r[5]} key={r[6]}"
                        )
                else:
                    print(f"{rn}: No refund-like entries found in payments")

            print("\nSummary:")
            print(f"{len(found)} of {len(reserves)} have refund-like entries recorded.")


if __name__ == "__main__":
    raise SystemExit(main())
