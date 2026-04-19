import csv
from pathlib import Path
import psycopg2

OUT_DIR = Path(r"L:\limo\archive\tmp_zip_analysis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHANGED_CSV = OUT_DIR / "normalize_8362_changed_rows.csv"
SUMMARY_TXT = OUT_DIR / "normalize_8362_summary.txt"

DB = dict(host="localhost", port=5432, dbname="almsdata", user="postgres", password="ArrowLimousine")

DATE_FROM = "2012-01-01"
DATE_TO = "2013-12-31"
ACCOUNT = "0228362"


def fetch_group_counts(cur):
    cur.execute(
        """
        SELECT
          CASE
            WHEN description ILIKE '%%GLOBAL SYSTEM DEPOSIT%%' THEN 'GLOBAL_SYSTEM_DEPOSIT'
            WHEN description ILIKE '%%GLOBAL SYSTEM WITHDRAW%%' THEN 'GLOBAL_SYSTEM_WITHDRAW'
            WHEN description ILIKE '%%VCARD DEPOSIT%%' THEN 'VCARD_DEPOSIT'
            WHEN description ILIKE '%%MCARD DEPOSIT%%' THEN 'MCARD_DEPOSIT'
            WHEN description ILIKE '%%CARD DEPOSIT%%' THEN 'CARD_DEPOSIT'
            WHEN description ILIKE '%%ACARD%%' OR description ILIKE '%%AMEX%%' THEN 'AMEX_OR_ACARD'
            ELSE 'OTHER'
          END AS grp,
          COUNT(*) cnt,
          ROUND(COALESCE(SUM(credit_amount),0)::numeric,2) credit_sum,
          ROUND(COALESCE(SUM(debit_amount),0)::numeric,2) debit_sum
        FROM banking_transactions
        WHERE account_number=%s
          AND transaction_date BETWEEN DATE %s AND DATE %s
        GROUP BY 1
        ORDER BY cnt DESC
        """,
        (ACCOUNT, DATE_FROM, DATE_TO),
    )
    return cur.fetchall()


def fetch_candidates(cur):
    cur.execute(
        """
        SELECT
            transaction_id,
            transaction_date,
            description AS old_description,
            debit_amount,
            credit_amount,
            CASE
                WHEN credit_amount IS NOT NULL AND (
                    description ILIKE '%%VCARD DEPOSIT%%'
                    OR description ILIKE '%%MCARD DEPOSIT%%'
                    OR description ILIKE '%%CARD DEPOSIT%%'
                    OR description ILIKE '%%ACARD DEPOSIT%%'
                ) THEN 'GLOBAL SYSTEM DEPOSIT'
                WHEN debit_amount IS NOT NULL AND (
                    description ILIKE '%%ACARD PAYMENT%%'
                    OR description ILIKE '%%MISC PAYMENT AMD#%%'
                    OR (description ILIKE '%%AMEX%%' AND description NOT ILIKE '%%DEPOSIT%%')
                    OR (description ILIKE '%%ACARD%%' AND description NOT ILIKE '%%DEPOSIT%%')
                ) THEN 'GLOBAL SYSTEM WITHDRAW'
                ELSE NULL
            END AS new_description
        FROM banking_transactions
        WHERE account_number=%s
          AND transaction_date BETWEEN DATE %s AND DATE %s
        ORDER BY transaction_date, transaction_id
        """,
        (ACCOUNT, DATE_FROM, DATE_TO),
    )
    rows = [r for r in cur.fetchall() if r[5] is not None]
    # Skip already-normalized rows
    rows = [r for r in rows if (r[2] or "").strip().upper() != (r[5] or "").strip().upper()]
    return rows


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    before = fetch_group_counts(cur)
    candidates = fetch_candidates(cur)

    # Apply updates in one transaction
    updated = 0
    for txn_id, tx_date, old_desc, debit_amt, credit_amt, new_desc in candidates:
        cur.execute(
            """
            UPDATE banking_transactions
            SET description = %s,
                updated_at = NOW()
            WHERE transaction_id = %s
            """,
            (new_desc, txn_id),
        )
        updated += cur.rowcount

    conn.commit()

    after = fetch_group_counts(cur)

    # Write changed rows CSV
    with open(CHANGED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "transaction_id",
            "transaction_date",
            "old_description",
            "new_description",
            "debit_amount",
            "credit_amount",
        ])
        for txn_id, tx_date, old_desc, debit_amt, credit_amt, new_desc in candidates:
            w.writerow([txn_id, tx_date, old_desc, new_desc, debit_amt, credit_amt])

    with open(SUMMARY_TXT, "w", encoding="utf-8") as f:
        f.write("8362 Label Normalization Summary (2012-2013)\n")
        f.write("=" * 80 + "\n")
        f.write(f"Account: {ACCOUNT}\n")
        f.write(f"Date range: {DATE_FROM} to {DATE_TO}\n")
        f.write(f"Rows updated: {updated}\n\n")

        f.write("Before:\n")
        for r in before:
            f.write(f"- {r[0]} | cnt={r[1]} | credit={r[2]} | debit={r[3]}\n")

        f.write("\nAfter:\n")
        for r in after:
            f.write(f"- {r[0]} | cnt={r[1]} | credit={r[2]} | debit={r[3]}\n")

        f.write("\nFiles:\n")
        f.write(f"- {CHANGED_CSV}\n")

    print(f"Rows updated: {updated}")
    print("Before groups:")
    for r in before:
        print(r)
    print("After groups:")
    for r in after:
        print(r)
    print(f"Wrote: {CHANGED_CSV}")
    print(f"Wrote: {SUMMARY_TXT}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
