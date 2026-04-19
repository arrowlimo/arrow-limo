import csv
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import psycopg2

BASE = Path(r"L:\limo\archive\tmp_zip_analysis")
MATCHED_DETAIL = BASE / "deep_dive_8362_vs_1615_6011_detail.csv"
OUT_DETAIL = BASE / "deep_dive_8362_unmatched_60_classified.csv"
OUT_SUMMARY = BASE / "deep_dive_8362_unmatched_60_summary.txt"

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")


def norm(s):
    return " ".join((s or "").strip().lower().split())


def classify(desc, side, amount):
    d = norm(desc)

    if "correction 00339" in d or "credit memo" in d:
        return "correction_memo", "keep_8362_as_system_correction"
    if "nsf return" in d or "nsf fee" in d or d.startswith("nsf"):
        return "nsf_adjustment", "keep_8362_nsf_flow"
    if "global system deposit" in d:
        return "card_settlement_deposit", "keep_8362_card_settlement"
    if "global system withdraw" in d or "acard payment" in d or "misc payment amd" in d:
        return "card_settlement_withdraw", "keep_8362_card_settlement"
    if "merchant services fee" in d or "account fee" in d or "overdraft" in d or "bank fee" in d:
        return "bank_fee_interest", "keep_8362_bank_charges"
    if "deposit" in d and side == "credit":
        return "generic_deposit", "review_source_then_keep"
    if "transfer" in d:
        return "transfer", "review_counterparty_transfer"
    if side == "debit" and amount is not None and amount >= Decimal("1000"):
        return "large_debit", "manual_review_high_value"
    return "other", "manual_review"


def main():
    matched_ids = set()
    with open(MATCHED_DETAIL, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                matched_ids.add(int(row["a_txn_id"]))
            except Exception:
                pass

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT transaction_id, account_number, transaction_date,
               debit_amount, credit_amount, description, check_number,
               receipt_id, reconciled_receipt_id, reconciliation_status, category
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND transaction_date BETWEEN DATE '2012-01-01' AND DATE '2013-12-31'
        ORDER BY transaction_date, transaction_id
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    unmatched = []
    for r in rows:
        txn_id = r[0]
        if txn_id in matched_ids:
            continue
        debit = Decimal(str(r[3])) if r[3] is not None else None
        credit = Decimal(str(r[4])) if r[4] is not None else None
        side = "debit" if debit is not None else "credit"
        amount = debit if debit is not None else credit
        desc = r[5] or ""
        bucket, action = classify(desc, side, amount)

        unmatched.append(
            {
                "txn_id": txn_id,
                "account": r[1] or "",
                "txn_date": r[2],
                "side": side,
                "amount": amount,
                "description": desc,
                "check_number": r[6] or "",
                "receipt_id": r[7] or "",
                "reconciled_receipt_id": r[8] or "",
                "reconciliation_status": r[9] or "",
                "category": r[10] or "",
                "bucket": bucket,
                "recommended_action": action,
            }
        )

    fields = [
        "txn_id",
        "account",
        "txn_date",
        "side",
        "amount",
        "description",
        "check_number",
        "receipt_id",
        "reconciled_receipt_id",
        "reconciliation_status",
        "category",
        "bucket",
        "recommended_action",
    ]

    with open(OUT_DETAIL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in unmatched:
            w.writerow(row)

    c_bucket = Counter(r["bucket"] for r in unmatched)
    amt_bucket = defaultdict(Decimal)
    for r in unmatched:
        amt_bucket[r["bucket"]] += Decimal(str(r["amount"]))

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("8362 Unmatched 60 Classification Summary\n")
        f.write("=" * 80 + "\n")
        f.write(f"Total unmatched rows: {len(unmatched)}\n\n")
        f.write("By bucket (count, total amount):\n")
        for b, n in c_bucket.most_common():
            f.write(f"- {b}: {n} | amount={amt_bucket[b]:.2f}\n")

    print(f"Total unmatched rows: {len(unmatched)}")
    print("Buckets:")
    for b, n in c_bucket.most_common():
        print(f"  {b}: {n} amount={amt_bucket[b]:.2f}")
    print(f"Wrote: {OUT_DETAIL}")
    print(f"Wrote: {OUT_SUMMARY}")


if __name__ == "__main__":
    main()
