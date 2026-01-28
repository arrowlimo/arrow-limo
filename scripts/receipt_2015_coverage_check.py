#!/usr/bin/env python3
"""
2015 Receipts Coverage Check
----------------------------
Computes monthly counts and totals from receipts for 2015 and extracts GST-included amounts
(using 5% GST as default for AB unless tax_rate column exists). Writes a simple Markdown report
and prints a short summary.

Safe and read-only. Uses api.get_db_connection to respect DB_* env vars.
"""
import pathlib
import sys
from decimal import Decimal
from typing import Dict, Tuple

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api import get_db_connection  # type: ignore

REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(exist_ok=True)
REPORT_PATH = REPORT_DIR / "receipts_2015_coverage.md"


def get_receipt_columns(cur):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='receipts'
        """
    )
    return {r[0].lower(): True for r in cur.fetchall()}


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    cols = get_receipt_columns(cur)
    # Determine column names defensively
    date_col = 'receipt_date' if cols.get('receipt_date') else 'date' if cols.get('date') else None
    amt_col = 'gross_amount' if cols.get('gross_amount') else 'amount' if cols.get('amount') else None
    gst_col = 'gst_amount' if cols.get('gst_amount') else None
    tax_rate_col = 'tax_rate' if cols.get('tax_rate') else None

    if not date_col or not amt_col:
        print("[FAIL] receipts table missing required columns for coverage check")
        return

    # Monthly summary
    cur.execute(
        f"""
        SELECT EXTRACT(MONTH FROM {date_col})::int as month,
               COUNT(*) as cnt,
               COALESCE(SUM({amt_col}), 0) as total
        FROM receipts
        WHERE {date_col} >= DATE '2015-01-01' AND {date_col} < DATE '2016-01-01'
        GROUP BY EXTRACT(MONTH FROM {date_col})
        ORDER BY month
        """
    )
    rows = cur.fetchall()

    # GST extraction (if gst_amount exists, use it; else compute with 5% included model)
    if gst_col:
        cur.execute(
            f"""
            SELECT COALESCE(SUM({gst_col}), 0)
            FROM receipts
            WHERE {date_col} >= DATE '2015-01-01' AND {date_col} < DATE '2016-01-01'
            """
        )
        total_gst = cur.fetchone()[0] or 0
    else:
        # Compute GST-included @ 5%
        cur.execute(
            f"""
            SELECT COALESCE(SUM(({amt_col} * 0.05 / 1.05)), 0)
            FROM receipts
            WHERE {date_col} >= DATE '2015-01-01' AND {date_col} < DATE '2016-01-01'
            """
        )
        total_gst = cur.fetchone()[0] or 0

    # Write report
    lines = []
    lines.append("# 2015 Receipts Coverage\n")
    lines.append("Month | Count | Total\n")
    lines.append("----- | -----:| -----:|\n")
    months_present = set()
    for m, cnt, total in rows:
        months_present.add(int(m))
        lines.append(f"{int(m):02d} | {int(cnt):>5} | ${float(total):>12,.2f}")
    lines.append("\n")
    lines.append(f"Total GST (included model if needed): ${float(total_gst):,.2f}\n")

    # Simple coverage note
    missing_months = [mm for mm in range(1,13) if mm not in months_present]
    if missing_months:
        lines.append(f"Missing months (no receipts): {', '.join(f'{m:02d}' for m in missing_months)}\n")
    else:
        lines.append("All months present with at least one receipt.\n")

    REPORT_PATH.write_text("\n".join(lines), encoding='utf-8')

    print("=== 2015 Receipts Coverage Summary ===")
    print(f"Months with receipts: {len(months_present)}/12")
    if missing_months:
        print(f"Missing months: {missing_months}")
    print(f"Report: {REPORT_PATH}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
