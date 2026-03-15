#!/usr/bin/env python3
"""
Banking 2015 Coverage Report
----------------------------
Summarizes 2015 banking_transactions by month (debits, credits) and shows top vendors by debit.
Read-only. Writes Markdown to reports/banking_2015_coverage.md.
"""
import pathlib
import sys
from typing import Dict

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api import get_db_connection  # type: ignore

REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(exist_ok=True)
REPORT_PATH = REPORT_DIR / "banking_2015_coverage.md"


def get_cols(cur) -> Dict[str, bool]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='banking_transactions'
        """
    )
    return {r[0].lower(): True for r in cur.fetchall()}


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    cols = get_cols(cur)
    date_col = 'transaction_date' if cols.get('transaction_date') else 'date' if cols.get('date') else None
    debit_col = 'debit_amount' if cols.get('debit_amount') else None
    credit_col = 'credit_amount' if cols.get('credit_amount') else None
    desc_col = 'description' if cols.get('description') else None
    vendor_col = 'vendor_name' if cols.get('vendor_name') else None

    if not date_col or not debit_col or not credit_col:
        print("[FAIL] Required columns missing in banking_transactions")
        return

    cur.execute(
        f"""
        SELECT EXTRACT(MONTH FROM {date_col})::int as month,
               COUNT(*) as cnt,
               COALESCE(SUM({debit_col}), 0) as total_debits,
               COALESCE(SUM({credit_col}), 0) as total_credits
        FROM banking_transactions
        WHERE {date_col} >= DATE '2015-01-01' AND {date_col} < DATE '2016-01-01'
        GROUP BY EXTRACT(MONTH FROM {date_col})
        ORDER BY month
        """
    )
    monthly = cur.fetchall()

    # Top vendors by total debit
    if vendor_col:
        cur.execute(
            f"""
            SELECT {vendor_col} as vendor,
                   COUNT(*) as cnt,
                   COALESCE(SUM({debit_col}), 0) as total_debit
            FROM banking_transactions
            WHERE {date_col} >= DATE '2015-01-01' AND {date_col} < DATE '2016-01-01'
              AND COALESCE({debit_col},0) > 0
            GROUP BY {vendor_col}
            ORDER BY total_debit DESC
            LIMIT 20
            """
        )
        top = cur.fetchall()
    else:
        top = []

    lines = []
    lines.append("# Banking 2015 Coverage\n")
    lines.append("Month | Txns | Total Debits | Total Credits\n")
    lines.append("----- | ----:| ------------:| ------------:|\n")
    months_present = set()
    for m, cnt, dsum, csum in monthly:
        months_present.add(int(m))
        lines.append(f"{int(m):02d} | {int(cnt):>4} | ${float(dsum):>12,.2f} | ${float(csum):>12,.2f}")

    missing = [mm for mm in range(1,13) if mm not in months_present]
    lines.append("\n")
    if missing:
        lines.append(f"Missing months (no bank txns): {', '.join(f'{m:02d}' for m in missing)}\n")
    else:
        lines.append("All months present with at least one transaction.\n")

    lines.append("\n## Top 20 Vendors by Debit (2015)\n")
    if top:
        lines.append("Vendor | Count | Total Debit\n")
        lines.append("-----  | ----: | ----------:|\n")
        for vendor, cnt, total in top:
            v = vendor or '(unknown)'
            lines.append(f"{v} | {int(cnt):>4} | ${float(total):>11,.2f}")
    else:
        lines.append("No vendor_name column; cannot summarize vendors.\n")

    REPORT_PATH.write_text("\n".join(lines), encoding='utf-8')

    print("=== Banking 2015 Coverage Summary ===")
    print(f"Months present: {len(months_present)}/12")
    print(f"Report: {REPORT_PATH}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
