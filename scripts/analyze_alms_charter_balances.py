import os
import csv
import psycopg2
from collections import defaultdict

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

OUT_SUMMARY = r"L:\limo\reports\ALMS_CHARTER_BALANCE_ANALYSIS.csv"
OUT_DISCREPANCIES = r"L:\limo\reports\ALMS_CHARTER_BALANCE_DISCREPANCIES.csv"


def main():
    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur = conn.cursor()

    # Get charters with charges and existing balance fields
    cur.execute("""
        SELECT 
            c.charter_id,
            c.reserve_number,
            c.total_amount_due,
            c.paid_amount,
            c.balance,
            c.status,
            c.client_id
        FROM charters c
        WHERE c.reserve_number IS NOT NULL
        ORDER BY c.reserve_number
    """)
    charters = []
    for r in cur.fetchall():
        charters.append({
            "charter_id": r[0],
            "reserve_number": r[1],
            "total_amount_due": float(r[2] or 0),
            "paid_amount": float(r[3] or 0),
            "balance": float(r[4] or 0),
            "status": r[5] or "",
            "client_id": r[6],
        })

    # Get payments per reserve_number
    cur.execute("""
        SELECT reserve_number, SUM(amount) as total_paid
        FROM payments
        WHERE reserve_number IS NOT NULL
        GROUP BY reserve_number
    """)
    payments_by_reserve = {}
    for r in cur.fetchall():
        payments_by_reserve[r[0]] = float(r[1] or 0)

    cur.close()
    conn.close()

    # Analysis
    total_charters = len(charters)
    total_charges = sum(c["total_amount_due"] for c in charters)
    total_paid_from_payments = sum(payments_by_reserve.values())
    total_paid_from_charters = sum(c["paid_amount"] for c in charters)
    total_balance_from_charters = sum(c["balance"] for c in charters)

    discrepancies = []
    matched = 0
    payment_mismatch = 0
    balance_mismatch = 0

    for c in charters:
        rn = c["reserve_number"]
        actual_paid = payments_by_reserve.get(rn, 0.0)
        calculated_balance = c["total_amount_due"] - actual_paid
        
        charter_paid = c["paid_amount"]
        charter_balance = c["balance"]

        paid_diff = abs(actual_paid - charter_paid)
        balance_diff = abs(calculated_balance - charter_balance)

        if paid_diff > 0.01 or balance_diff > 0.01:
            discrepancies.append({
                "reserve_number": rn,
                "charter_id": c["charter_id"],
                "status": c["status"],
                "total_amount_due": c["total_amount_due"],
                "actual_paid": actual_paid,
                "charter_paid": charter_paid,
                "paid_diff": round(actual_paid - charter_paid, 2),
                "calculated_balance": round(calculated_balance, 2),
                "charter_balance": charter_balance,
                "balance_diff": round(calculated_balance - charter_balance, 2),
            })
            if paid_diff > 0.01:
                payment_mismatch += 1
            if balance_diff > 0.01:
                balance_mismatch += 1
        else:
            matched += 1

    # Write summary
    os.makedirs(os.path.dirname(OUT_SUMMARY), exist_ok=True)
    with open(OUT_SUMMARY, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Value"])
        w.writerow(["Total Charters", total_charters])
        w.writerow(["Total Charges", f"${total_charges:,.2f}"])
        w.writerow(["Total Paid (from payments table)", f"${total_paid_from_payments:,.2f}"])
        w.writerow(["Total Paid (from charters.paid_amount)", f"${total_paid_from_charters:,.2f}"])
        w.writerow(["Total Balance (from charters.balance)", f"${total_balance_from_charters:,.2f}"])
        w.writerow([""])
        w.writerow(["Charters Matched", matched])
        w.writerow(["Charters with Payment Discrepancy", payment_mismatch])
        w.writerow(["Charters with Balance Discrepancy", balance_mismatch])
        w.writerow(["Total Discrepancies", len(discrepancies)])

    # Write discrepancies
    if discrepancies:
        with open(OUT_DISCREPANCIES, "w", newline="", encoding="utf-8") as f:
            fieldnames = [
                "reserve_number", "charter_id", "status", "total_amount_due",
                "actual_paid", "charter_paid", "paid_diff",
                "calculated_balance", "charter_balance", "balance_diff"
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for d in sorted(discrepancies, key=lambda x: abs(x["balance_diff"]), reverse=True):
                w.writerow(d)

    print(f"Total Charters: {total_charters}")
    print(f"Total Charges: ${total_charges:,.2f}")
    print(f"Total Paid (payments table): ${total_paid_from_payments:,.2f}")
    print(f"Total Paid (charters.paid_amount): ${total_paid_from_charters:,.2f}")
    print(f"Total Balance (charters.balance): ${total_balance_from_charters:,.2f}")
    print(f"")
    print(f"Matched: {matched}")
    print(f"Payment Discrepancies: {payment_mismatch}")
    print(f"Balance Discrepancies: {balance_mismatch}")
    print(f"Total Discrepancies: {len(discrepancies)}")
    print(f"")
    print(f"Summary: {OUT_SUMMARY}")
    print(f"Discrepancies: {OUT_DISCREPANCIES}")


if __name__ == "__main__":
    main()
