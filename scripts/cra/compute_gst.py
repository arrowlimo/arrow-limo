#!/usr/bin/env python
"""
Compute GST/HST for a period and persist results to tax tables.
- Reads revenue from charters (tax-included at 5%).
- Reads ITCs from receipts.gst_amount.
- Writes tax_periods, tax_returns, tax_variances.
"""

import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import List, Tuple

try:
    from .db import get_connection
    from .periods import parse_period
except Exception:  # pragma: no cover
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
    from db import get_connection  # type: ignore
    from periods import parse_period  # type: ignore

GST_RATE = Decimal("0.05")


def q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute(period_label: str) -> Tuple[dict, List[dict]]:
    p = parse_period(period_label)
    params = {
        "start": p.start,
        "end": p.end,
    }
    values: dict = {
        "period": p.label,
        "start_date": p.start,
        "end_date": p.end,
    }
    variances: List[dict] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(total_amount_due), 0)
                FROM charters
                WHERE charter_date >= %(start)s AND charter_date <= %(end)s
                """,
                params,
            )
            revenue = Decimal(str(cur.fetchone()[0] or 0))

            gst_collected = q(revenue * GST_RATE / (Decimal("1") + GST_RATE))
            values.update({
                "revenue": q(revenue),
                "gst_collected": gst_collected,
            })

            cur.execute(
                """
                SELECT COALESCE(SUM(gst_amount), 0)
                FROM receipts
                WHERE receipt_date >= %(start)s AND receipt_date <= %(end)s
                """,
                params,
            )
            gst_paid = Decimal(str(cur.fetchone()[0] or 0))
            gst_paid = q(gst_paid)
            values["gst_paid"] = gst_paid

            net = q(gst_collected - gst_paid)
            values["net_gst"] = net

            # Checks
            if revenue > 0:
                rate = (gst_collected / revenue * Decimal("100"))
                if rate < Decimal("4.5"):
                    variances.append({
                        "field": "Line105_TotalGSTHSTCollected",
                        "severity": "high",
                        "actual": float(q(rate)),
                        "expected": 5.0,
                        "message": f"GST rate low at {rate:.2f}% (revenue likely tax-included or partially exempt)",
                        "recommendation": "Verify revenue composition and GST treatment."
                    })
                elif rate > Decimal("5.5"):
                    variances.append({
                        "field": "Line105_TotalGSTHSTCollected",
                        "severity": "medium",
                        "actual": float(q(rate)),
                        "expected": 5.0,
                        "message": f"GST rate high at {rate:.2f}% (possible over-collection)",
                        "recommendation": "Review GST calculation on sales."
                    })
            if gst_paid == 0:
                variances.append({
                    "field": "Line108_ITCs",
                    "severity": "high",
                    "actual": float(gst_paid),
                    "expected": None,
                    "message": "No ITCs claimed. Expenses may be missing GST capture.",
                    "recommendation": "Confirm receipts.gst_amount is populated for purchases."
                })
            if net < 0:
                variances.append({
                    "field": "Line114_NetTaxToRemit",
                    "severity": "info",
                    "actual": float(net),
                    "expected": None,
                    "message": "Net GST is a refund.",
                    "recommendation": "Ensure instalments/remittances are reflected."
                })

    return values, variances


def persist(period_label: str, values: dict, variances: List[dict]) -> None:
    p = parse_period(period_label)
    quarter = None
    if p.label.endswith("Q1"):
        quarter = 1
    elif p.label.endswith("Q2"):
        quarter = 2
    elif p.label.endswith("Q3"):
        quarter = 3
    elif p.label.endswith("Q4"):
        quarter = 4
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tax_periods (label, period_type, start_date, end_date, year, quarter)
                VALUES (%s, 'gst', %s, %s, %s, %s)
                ON CONFLICT (label) DO UPDATE
                  SET start_date = EXCLUDED.start_date,
                      end_date = EXCLUDED.end_date,
                      year = EXCLUDED.year,
                      quarter = EXCLUDED.quarter
                RETURNING id
                """,
                (p.label, p.start, p.end, p.start.year, quarter),
            )
            period_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO tax_returns (period_id, form_type, status, calculated_amount, notes, updated_at)
                VALUES (%s, 'gst', 'calculated', %s, %s, NOW())
                ON CONFLICT (period_id, form_type) DO UPDATE
                  SET calculated_amount = EXCLUDED.calculated_amount,
                      status = EXCLUDED.status,
                      notes = EXCLUDED.notes,
                      updated_at = NOW()
                RETURNING id
                """,
                (period_id, float(values["net_gst"]), "GST auto-computed"),
            )
            return_id = cur.fetchone()[0]

            cur.execute("DELETE FROM tax_variances WHERE tax_return_id = %s", (return_id,))
            for v in variances:
                cur.execute(
                    """
                    INSERT INTO tax_variances (tax_return_id, field, actual, expected, severity, message, recommendation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        return_id,
                        v.get("field"),
                        v.get("actual"),
                        v.get("expected"),
                        v.get("severity", "info"),
                        v.get("message"),
                        v.get("recommendation"),
                    ),
                )
        conn.commit()


def fmt(values: dict) -> str:
    return " | ".join([
        f"Period {values['period']}",
        f"Revenue ${values['revenue']:,.2f}",
        f"GST Collected ${values['gst_collected']:,.2f}",
        f"GST Paid ${values['gst_paid']:,.2f}",
        f"Net ${values['net_gst']:,.2f}",
    ])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", required=True, help="e.g. 2025Q4, 2025, 2025-01..2025-03")
    ap.add_argument("--write", action="store_true", help="Persist results to DB (tax_* tables)")
    args = ap.parse_args()

    values, issues = compute(args.period)
    print(fmt(values))
    if issues:
        print("Issues:")
        for v in issues:
            sev = v.get("severity", "info").upper()
            print(f" - [{sev}] {v.get('field')}: {v.get('message')}")

    if args.write:
        persist(args.period, values, issues)
        print("✅ Saved to tax_returns/tax_variances")
    else:
        print("(dry-run: no DB writes)")


if __name__ == "__main__":
    main()
