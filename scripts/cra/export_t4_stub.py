#!/usr/bin/env python
"""
Stub T4/T4 Summary exporter.
Aggregates annual payroll totals and writes a simple CSV summary for reference.
This is a placeholder until full CRA XML/PDF generation is implemented.
"""

import argparse
import csv
from pathlib import Path
from decimal import Decimal

try:
    from .db import get_connection
except Exception:  # pragma: no cover
    import sys
    sys.path.append(str(Path(__file__).resolve().parent))
    from db import get_connection  # type: ignore


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", required=True, help="Year, e.g. 2025")
    ap.add_argument("--output", help="Output CSV path", default=None)
    args = ap.parse_args()

    try:
        year = int(args.period[:4])
    except Exception:
        raise SystemExit("--period must be a 4-digit year for T4 stub")

    out_path = Path(args.output) if args.output else Path(f"L:/limo/reports/T4_summary_{year}.csv")
    rows = []

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(dp.employee_id::text, dp.driver_id, 'unknown') AS employee_id,
                       COALESCE(e.full_name, e.name, dp.driver_id, 'Unknown') AS employee_name,
                       COALESCE(SUM(dp.gross_pay), 0) AS gross_pay,
                       COALESCE(SUM(dp.cpp), 0) AS cpp,
                       COALESCE(SUM(dp.ei), 0) AS ei,
                       COALESCE(SUM(dp.tax), 0) AS tax
                FROM driver_payroll dp
                LEFT JOIN employees e ON dp.employee_id = e.employee_id OR dp.driver_id = e.driver_code
                WHERE dp.year = %s
                GROUP BY dp.employee_id, dp.driver_id, e.full_name, e.name
                ORDER BY employee_id
                """,
                (year,)
            )
            for r in cur.fetchall():
                emp_id, name, gross, cpp, ei, tax = r
                rows.append({
                    "employee_id": emp_id,
                    "employee_name": name,
                    "gross_pay": f"{Decimal(str(gross or 0)):.2f}",
                    "cpp": f"{Decimal(str(cpp or 0)):.2f}",
                    "ei": f"{Decimal(str(ei or 0)):.2f}",
                    "tax": f"{Decimal(str(tax or 0)):.2f}",
                })

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["employee_id", "employee_name", "gross_pay", "cpp", "ei", "tax"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"✅ Wrote {out_path} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
