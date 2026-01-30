"""Report gratuity (tips) vs payroll wages for a given month (default August 2012).

This script:
- Sums gratuity from charters (prefers explicit amount fields; optionally estimates from percent when amount is missing).
- Groups by assigned_driver_id (employee_id); unlinked rows grouped by driver_name.
- Compares with driver_payroll gross_pay for the same month (WAGE/BACKFILL only).
- Prints a concise per-driver and aggregate summary.

Usage:
  python -X utf8 scripts/report_gratuity_vs_payroll_august_2012.py --year 2012 --month 8

Environment variables (DB_*) are used for database connection.
"""

from __future__ import annotations

import argparse
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Any, Tuple

import psycopg2
import psycopg2.extras


def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "almsdata")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "***REDACTED***")
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def table_columns(conn, table: str) -> Dict[str, str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    out = {r[0]: r[1] for r in cur.fetchall()}
    cur.close()
    return out


def parse_args():
    p = argparse.ArgumentParser(description="Gratuity vs payroll report for a given month.")
    p.add_argument("--year", type=int, default=2012)
    p.add_argument("--month", type=int, default=8)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


@dataclass
class DriverGratuity:
    employee_id: int | None
    driver_name: str | None
    gratuity_actual: float = 0.0
    gratuity_estimated: float = 0.0
    charter_count_with_grat: int = 0


def fetch_charter_gratuities(conn, year: int, month: int) -> Dict[Tuple[int | None, str | None], DriverGratuity]:
    cols = table_columns(conn, 'charters')
    # Build dynamic select list
    sel = [
        "assigned_driver_id" if "assigned_driver_id" in cols else "NULL AS assigned_driver_id",
        "driver_name" if "driver_name" in cols else "NULL AS driver_name",
        "rate" if "rate" in cols else "NULL AS rate",
        "driver_gratuity_amount" if "driver_gratuity_amount" in cols else "NULL AS driver_gratuity_amount",
        "driver_gratuity" if "driver_gratuity" in cols else "NULL AS driver_gratuity",
        "driver_gratuity_percent" if "driver_gratuity_percent" in cols else "NULL AS driver_gratuity_percent",
        "charter_date" if "charter_date" in cols else "NULL AS charter_date",
    ]

    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"""
        SELECT {', '.join(sel)}
        FROM charters
        WHERE DATE(charter_date) >= %s AND DATE(charter_date) <= %s
        """,
        (f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-31"),
    )
    rows = cur.fetchall()
    cur.close()

    agg: Dict[Tuple[int | None, str | None], DriverGratuity] = {}
    for r in rows:
        employee_id = r.get("assigned_driver_id")
        driver_name = r.get("driver_name")
        rate = r.get("rate") or 0.0
        g_amt = r.get("driver_gratuity_amount")
        g_raw = r.get("driver_gratuity")
        g_pct = r.get("driver_gratuity_percent")

        # Normalize numeric fields
        try:
            rate = float(rate) if rate is not None else 0.0
        except Exception:
            rate = 0.0
        try:
            g_amt_v = float(g_amt) if g_amt is not None else 0.0
        except Exception:
            g_amt_v = 0.0
        try:
            g_raw_v = float(g_raw) if g_raw is not None else 0.0
        except Exception:
            g_raw_v = 0.0
        try:
            g_pct_v = float(g_pct) if g_pct is not None else 0.0
        except Exception:
            g_pct_v = 0.0

        actual = g_amt_v if g_amt_v > 0 else g_raw_v if g_raw_v > 0 else 0.0

        # Estimate from percent only when actual amount is zero and percent looks valid and rate > 0.
        estimated = 0.0
        if actual <= 0 and g_pct_v and rate > 0:
            pct = g_pct_v / 100.0 if g_pct_v > 1 else g_pct_v
            if 0 < pct <= 1.0:
                estimated = round(rate * pct, 2)

        key = (employee_id, driver_name)
        if key not in agg:
            agg[key] = DriverGratuity(employee_id=employee_id, driver_name=driver_name)
        agg[key].gratuity_actual += actual
        agg[key].gratuity_estimated += estimated
        if actual > 0 or estimated > 0:
            agg[key].charter_count_with_grat += 1

    return agg


def fetch_payroll_gross(conn, year: int, month: int) -> Dict[int, float]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_id, COALESCE(SUM(gross_pay),0) AS gross
        FROM driver_payroll
        WHERE year=%s AND month=%s
          AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
        GROUP BY employee_id
        """,
        (year, month),
    )
    result = {}
    for eid, gross in cur.fetchall():
        if eid is None:
            continue
        result[int(eid)] = float(gross or 0)
    cur.close()
    return result


def main():
    args = parse_args()
    conn = get_db_connection()
    try:
        grat = fetch_charter_gratuities(conn, args.year, args.month)
        payroll_gross = fetch_payroll_gross(conn, args.year, args.month)

        # Aggregate totals
        total_actual = sum(v.gratuity_actual for v in grat.values())
        total_est = sum(v.gratuity_estimated for v in grat.values())
        total_payroll = sum(payroll_gross.values())

        print(f"Gratuity vs Payroll - {args.year}-{args.month:02d}")
        print("================================================")
        print(f"Total Payroll Gross (WAGE/BACKFILL): {total_payroll:,.2f}")
        print(f"Total Gratuity (actual from charters): {total_actual:,.2f}")
        print(f"Total Gratuity (estimated from percent): {total_est:,.2f}")
        print()
        header = f"{'EmpID':>6}  {'Name':<28}  {'Grat Actual':>12}  {'Grat Est':>10}  {'Charters':>8}  {'Payroll Gross':>14}"
        print(header)
        print('-'*len(header))

        # Sort: linked employees first (by id), then unlinked by name
        def sort_key(item):
            (eid, name), v = item
            return (0 if eid is not None else 1, eid or 0, name or "")

        for (eid, name), v in sorted(grat.items(), key=sort_key):
            pg = payroll_gross.get(eid or -1, 0.0)
            display_name = (name or "").strip()[:28]
            if eid is None:
                display_name = f"UNLINKED: {display_name}" if display_name else "UNLINKED"
            print(f"{str(eid) if eid is not None else '-':>6}  {display_name:<28}  {v.gratuity_actual:>12.2f}  {v.gratuity_estimated:>10.2f}  {v.charter_count_with_grat:>8}  {pg:>14.2f}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
