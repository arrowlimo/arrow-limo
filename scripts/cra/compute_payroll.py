#!/usr/bin/env python
"""
Compute payroll remittance totals for a year and persist to tax tables.
- Aggregates driver_payroll (gross_pay, cpp, ei, tax) by year.
- Computes employer CPP match and employer EI (1.4x employee EI).
- Writes tax_returns/tax_variances with form_type='payroll'.
"""

import argparse
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import List, Tuple

try:
    from .db import get_connection
except Exception:  # pragma: no cover
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
    from db import get_connection  # type: ignore


def q(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute(year: int) -> Tuple[dict, List[dict]]:
    values: dict = {"year": year}
    variances: List[dict] = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(gross_pay), 0),
                       COALESCE(SUM(cpp), 0),
                       COALESCE(SUM(ei), 0),
                       COALESCE(SUM(tax), 0)
                FROM driver_payroll
                WHERE year = %s
                """,
                (year,),
            )
            row = cur.fetchone()
            gross = Decimal(str(row[0] or 0))
            cpp = Decimal(str(row[1] or 0))
            ei = Decimal(str(row[2] or 0))
            tax = Decimal(str(row[3] or 0))

            employer_cpp = cpp
            employer_ei = ei * Decimal("1.4")
            remittance = cpp + employer_cpp + ei + employer_ei + tax

            values.update({
                "gross_pay": q(gross),
                "cpp": q(cpp),
                "ei": q(ei),
                "tax": q(tax),
                "employer_cpp": q(employer_cpp),
                "employer_ei": q(employer_ei),
                "remittance": q(remittance),
            })

            # Variances
            cur.execute(
                """
                SELECT COUNT(*)
                FROM driver_payroll
                WHERE year = %s AND gross_pay > 0 AND (
                    cpp IS NULL OR cpp = 0 OR ei IS NULL OR ei = 0 OR tax IS NULL OR tax = 0
                )
                """,
                (year,),
            )
            missing = cur.fetchone()[0] or 0
            if missing:
                variances.append({
                    "field": "payroll_deductions",
                    "severity": "high",
                    "actual": float(missing),
                    "expected": None,
                    "message": f"{missing} payroll rows missing CPP/EI/Tax despite gross pay.",
                    "recommendation": "Populate CPP/EI/tax for all paid rows before filing.",
                })

    return values, variances


def persist(year: int, values: dict, variances: List[dict]) -> None:
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    label = str(year)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tax_periods (label, period_type, start_date, end_date, year, quarter)
                VALUES (%s, 'payroll', %s, %s, %s, NULL)
                ON CONFLICT (label) DO UPDATE
                  SET start_date = EXCLUDED.start_date,
                      end_date = EXCLUDED.end_date,
                      year = EXCLUDED.year,
                      quarter = NULL
                RETURNING id
                """,
                (label, start, end, year),
            )
            period_id = cur.fetchone()[0]

            cur.execute(
                """
                INSERT INTO tax_returns (period_id, form_type, status, calculated_amount, notes, updated_at)
                VALUES (%s, 'payroll', 'calculated', %s, %s, NOW())
                ON CONFLICT (period_id, form_type) DO UPDATE
                  SET calculated_amount = EXCLUDED.calculated_amount,
                      status = EXCLUDED.status,
                      notes = EXCLUDED.notes,
                      updated_at = NOW()
                RETURNING id
                """,
                (period_id, float(values["remittance"]), "Payroll auto-computed"),
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
        f"Year {values['year']}",
        f"Gross ${values['gross_pay']:,.2f}",
        f"CPP ${values['cpp']:,.2f}",
        f"EI ${values['ei']:,.2f}",
        f"Tax ${values['tax']:,.2f}",
        f"Remit ${values['remittance']:,.2f}",
    ])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", required=True, help="Year, e.g. 2025")
    ap.add_argument("--write", action="store_true", help="Persist results to DB (tax_* tables)")
    args = ap.parse_args()

    try:
        year = int(args.period[:4])
    except Exception:
        raise SystemExit("--period must be a 4-digit year for payroll")

    values, issues = compute(year)
    print(fmt(values))
    if issues:
        print("Issues:")
        for v in issues:
            sev = v.get("severity", "info").upper()
            print(f" - [{sev}] {v.get('field')}: {v.get('message')}")

    if args.write:
        persist(year, values, issues)
        print("✅ Saved to tax_returns/tax_variances")
    else:
        print("(dry-run: no DB writes)")


if __name__ == "__main__":
    main()
