import csv
from collections import Counter
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import psycopg2

OUT_DIR = Path(r"L:\limo\archive\tmp_zip_analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_DETAIL = OUT_DIR / "deep_dive_8362_vs_1615_6011_detail.csv"
OUT_SUMMARY = OUT_DIR / "deep_dive_8362_vs_1615_6011_summary.txt"

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

D1 = "2012-01-01"
D2 = "2013-12-31"


def norm(s):
    return " ".join((s or "").lower().replace("'", "").split())


def fetch_rows(cur, account_filter):
    cur.execute(
        """
        SELECT transaction_id, account_number, transaction_date,
               debit_amount, credit_amount, description, check_number,
               receipt_id, reconciled_receipt_id, reconciliation_status
        FROM banking_transactions
        WHERE transaction_date BETWEEN DATE %s AND DATE %s
          AND """
        + account_filter
        + """
        ORDER BY transaction_date, transaction_id
        """,
        (D1, D2),
    )
    rows = []
    for r in cur.fetchall():
        amt = None
        side = ""
        if r[3] is not None:
            amt = Decimal(str(r[3]))
            side = "debit"
        elif r[4] is not None:
            amt = Decimal(str(r[4]))
            side = "credit"
        if amt is None:
            continue
        rows.append(
            {
                "transaction_id": r[0],
                "account_number": (r[1] or "").strip(),
                "transaction_date": r[2],
                "amount": amt,
                "side": side,
                "description": r[5] or "",
                "description_norm": norm(r[5] or ""),
                "check_number": (r[6] or "").strip(),
                "receipt_id": r[7],
                "reconciled_receipt_id": r[8],
                "reconciliation_status": r[9] or "",
            }
        )
    return rows


def find_best_matches(base, pool, day_window=3):
    results = []
    unmatched = 0
    for a in base:
        cands = []
        for b in pool:
            if a["transaction_id"] == b["transaction_id"]:
                continue
            if a["amount"] != b["amount"]:
                continue
            if a["side"] != b["side"]:
                continue
            dd = abs((a["transaction_date"] - b["transaction_date"]).days)
            if dd > day_window:
                continue
            desc_exact = int(a["description_norm"] == b["description_norm"] and a["description_norm"] != "")
            chk_exact = int(a["check_number"] != "" and a["check_number"] == b["check_number"])
            cands.append((dd, -chk_exact, -desc_exact, b, chk_exact, desc_exact))

        if cands:
            cands.sort(key=lambda x: (x[0], x[1], x[2]))
            best = cands[0]
            b = best[3]
            results.append(
                {
                    "a_txn_id": a["transaction_id"],
                    "a_account": a["account_number"],
                    "a_date": a["transaction_date"],
                    "a_side": a["side"],
                    "a_amount": a["amount"],
                    "a_desc": a["description"],
                    "a_check": a["check_number"],
                    "a_receipt": a["receipt_id"] or "",
                    "a_reconciled_receipt": a["reconciled_receipt_id"] or "",
                    "a_status": a["reconciliation_status"],
                    "b_txn_id": b["transaction_id"],
                    "b_account": b["account_number"],
                    "b_date": b["transaction_date"],
                    "b_side": b["side"],
                    "b_amount": b["amount"],
                    "b_desc": b["description"],
                    "b_check": b["check_number"],
                    "b_receipt": b["receipt_id"] or "",
                    "b_reconciled_receipt": b["reconciled_receipt_id"] or "",
                    "b_status": b["reconciliation_status"],
                    "day_diff": abs((a["transaction_date"] - b["transaction_date"]).days),
                    "check_exact": best[4],
                    "desc_exact": best[5],
                    "match_quality": (
                        "HIGH"
                        if best[4] == 1 or best[5] == 1
                        else "MEDIUM"
                    ),
                }
            )
        else:
            unmatched += 1

    return results, unmatched


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    tx_8362 = fetch_rows(cur, "account_number = '0228362'")
    tx_1615 = fetch_rows(cur, "account_number = '1615'")
    tx_6011 = fetch_rows(cur, "account_number = '903990106011'")

    matches_1615, unmatched_1615 = find_best_matches(tx_8362, tx_1615, day_window=3)
    matches_6011, unmatched_6011 = find_best_matches(tx_8362, tx_6011, day_window=3)

    # Prefer better match between 1615/6011 per 8362 txn
    best_by_8362 = {}

    def score(r):
        return (
            2 if r["match_quality"] == "HIGH" else 1,
            1 if r["check_exact"] == 1 else 0,
            1 if r["desc_exact"] == 1 else 0,
            -int(r["day_diff"]),
        )

    for r in matches_1615 + matches_6011:
        k = r["a_txn_id"]
        if k not in best_by_8362 or score(r) > score(best_by_8362[k]):
            best_by_8362[k] = r

    best_rows = list(best_by_8362.values())
    best_rows.sort(key=lambda x: (x["a_date"], x["a_txn_id"]))

    fields = [
        "a_txn_id",
        "a_account",
        "a_date",
        "a_side",
        "a_amount",
        "a_desc",
        "a_check",
        "a_receipt",
        "a_reconciled_receipt",
        "a_status",
        "b_txn_id",
        "b_account",
        "b_date",
        "b_side",
        "b_amount",
        "b_desc",
        "b_check",
        "b_receipt",
        "b_reconciled_receipt",
        "b_status",
        "day_diff",
        "check_exact",
        "desc_exact",
        "match_quality",
    ]

    with open(OUT_DETAIL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(best_rows)

    # summary
    cnt_by_b_account = Counter(r["b_account"] for r in best_rows)
    cnt_by_quality = Counter(r["match_quality"] for r in best_rows)

    matched_8362 = len(best_rows)
    total_8362 = len(tx_8362)
    unmatched_final = total_8362 - matched_8362

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write("Deep Dive: 8362 Origins vs 1615/6011 (2012-2013)\n")
        f.write("=" * 90 + "\n")
        f.write(f"8362 tx count: {total_8362}\n")
        f.write(f"1615 tx count: {len(tx_1615)}\n")
        f.write(f"6011 tx count: {len(tx_6011)}\n")
        f.write(f"8362 with likely counterpart in 1615/6011: {matched_8362}\n")
        f.write(f"8362 with no counterpart in 1615/6011 (<=3d same amount/side): {unmatched_final}\n")
        f.write("\nLikely counterpart account split:\n")
        for k, v in cnt_by_b_account.most_common():
            f.write(f"- {k}: {v}\n")
        f.write("\nMatch quality:\n")
        for k, v in cnt_by_quality.most_common():
            f.write(f"- {k}: {v}\n")

    print(f"8362 tx count: {total_8362}")
    print(f"1615 tx count: {len(tx_1615)}")
    print(f"6011 tx count: {len(tx_6011)}")
    print(f"8362 with likely counterpart in 1615/6011: {matched_8362}")
    print(f"8362 with no counterpart in 1615/6011: {unmatched_final}")
    print(f"Wrote: {OUT_DETAIL}")
    print(f"Wrote: {OUT_SUMMARY}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
