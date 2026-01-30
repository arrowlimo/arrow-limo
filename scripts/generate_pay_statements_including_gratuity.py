"""Generate monthly pay statements per employee including gratuity (configurable).

This produces per-month and YTD statements that combine wage gross from driver_payroll
with gratuity sourced from charters. Gratuity inclusion policy is configurable:

  --include-gratuity all            -> include all recorded charter gratuities
  --include-gratuity controlled     -> include only gratuities considered 'controlled'
                                      (heuristic: charter has at least one card/Square payment)
  --include-gratuity none           -> exclude gratuity (acts like wage-only baseline)

Outputs two CSV files in ./reports:
  - pay_plus_gratuity_{year}_detail.csv   (employee x month)
  - pay_plus_gratuity_{year}_summary.csv  (employee YTD + T4 comparison)

Notes:
  - We DO NOT recompute CPP/EI/Tax for gratuity here. We surface combined_gross so you can
    see Box 14 alignment when gratuity is controlled. Box 16/18/22 will differ unless backfilled.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, Tuple, Iterable

import psycopg2
import psycopg2.extras


def get_db_connection():
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "almsdata")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "***REDACTED***")
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def ensure_reports_dir() -> str:
    outdir = os.path.join(os.getcwd(), "reports")
    os.makedirs(outdir, exist_ok=True)
    return outdir


def table_columns(conn, table: str):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    cols = {r[0] for r in cur.fetchall()}
    cur.close()
    return cols


def employee_names(conn) -> Dict[int, str]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT employee_id, full_name FROM employees")
    except Exception:
        return {}
    m = {}
    for eid, name in cur.fetchall():
        if eid is None:
            continue
        m[int(eid)] = name or ""
    cur.close()
    return m


def fetch_wage_monthly(conn, year: int):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT employee_id, month,
               COALESCE(SUM(gross_pay),0) AS gross,
               COALESCE(SUM(cpp),0) AS cpp,
               COALESCE(SUM(ei),0) AS ei,
               COALESCE(SUM(tax),0) AS tax,
               COALESCE(SUM(net_pay),0) AS net
        FROM driver_payroll
        WHERE year=%s
          AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
        GROUP BY employee_id, month
        """,
        (year,),
    )
    rows = cur.fetchall()
    cur.close()
    out = defaultdict(lambda: defaultdict(lambda: {"gross":0.0,"cpp":0.0,"ei":0.0,"tax":0.0,"net":0.0}))
    for eid, month, gross, cpp, ei, tax, net in rows:
        if eid is None or month is None:
            continue
        out[int(eid)][int(month)] = {
            "gross": float(gross or 0),
            "cpp": float(cpp or 0),
            "ei": float(ei or 0),
            "tax": float(tax or 0),
            "net": float(net or 0),
        }
    return out


def payment_is_cardlike(r: Dict[str, any]) -> bool:
    pm = (r.get("payment_method") or r.get("qb_payment_type") or "").lower()
    if any(k in pm for k in ["visa", "master", "amex", "credit", "square", "card"]):
        return True
    # Square specific signals
    if r.get("square_status") or r.get("square_payment_id") or r.get("square_gross_sales"):
        return True
    return False


def build_controlled_gratuity_set(conn, year: int, month: int) -> set:
    """Return reserve_numbers that have card-like payments in given period."""
    cols = table_columns(conn, 'payments')
    sel = [
        "reserve_number" if "reserve_number" in cols else "NULL AS reserve_number",
        "payment_method" if "payment_method" in cols else "NULL AS payment_method",
        "qb_payment_type" if "qb_payment_type" in cols else "NULL AS qb_payment_type",
        "square_payment_id" if "square_payment_id" in cols else "NULL AS square_payment_id",
        "square_status" if "square_status" in cols else "NULL AS square_status",
        "square_gross_sales" if "square_gross_sales" in cols else "NULL AS square_gross_sales",
        "payment_date" if "payment_date" in cols else "created_at AS payment_date",
    ]
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"""
        SELECT {', '.join(sel)}
        FROM payments
        WHERE DATE(payment_date) >= %s AND DATE(payment_date) <= %s
          AND reserve_number IS NOT NULL
        """,
        (start_date, end_date),
    )
    cardlike = set()
    for r in cur.fetchall():
        if payment_is_cardlike(r):
            rn = r.get("reserve_number")
            if rn:
                cardlike.add(str(rn))
    cur.close()
    return cardlike


def fetch_gratuity_by_driver(conn, year: int, month: int, include_policy: str) -> Dict[int, float]:
    cols = table_columns(conn, 'charters')
    sel = [
        "assigned_driver_id" if "assigned_driver_id" in cols else "NULL AS assigned_driver_id",
        "reserve_number" if "reserve_number" in cols else "NULL AS reserve_number",
        "rate" if "rate" in cols else "NULL AS rate",
        "driver_gratuity_amount" if "driver_gratuity_amount" in cols else "NULL AS driver_gratuity_amount",
        "driver_gratuity" if "driver_gratuity" in cols else "NULL AS driver_gratuity",
        "driver_gratuity_percent" if "driver_gratuity_percent" in cols else "NULL AS driver_gratuity_percent",
        "charter_date" if "charter_date" in cols else "NULL AS charter_date",
    ]
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    start_date = f"{year:04d}-{month:02d}-01"
    end_date = f"{year:04d}-{month:02d}-{last_day:02d}"
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"""
        SELECT {', '.join(sel)}
        FROM charters
        WHERE DATE(charter_date) >= %s AND DATE(charter_date) <= %s
        """,
        (start_date, end_date),
    )
    rows = cur.fetchall()
    cur.close()

    controlled_reserves = set()
    if include_policy == "controlled":
        controlled_reserves = build_controlled_gratuity_set(conn, year, month)

    totals = defaultdict(float)
    for r in rows:
        eid = r.get("assigned_driver_id")
        if eid is None:
            continue
        rn = r.get("reserve_number")
        rate = r.get("rate") or 0.0
        g_amt = r.get("driver_gratuity_amount")
        g_raw = r.get("driver_gratuity")
        g_pct = r.get("driver_gratuity_percent")
        try:
            rate = float(rate) if rate is not None else 0.0
        except Exception:
            rate = 0.0
        for_var = [g_amt, g_raw, g_pct]
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
        if actual <= 0 and g_pct_v and rate > 0:
            pct = g_pct_v / 100.0 if g_pct_v > 1 else g_pct_v
            if 0 < pct <= 1.0:
                actual = round(rate * pct, 2)

        include = False
        if include_policy == "all":
            include = True
        elif include_policy == "none":
            include = False
        elif include_policy == "controlled":
            include = str(rn) in controlled_reserves if rn is not None else False
        if include and actual > 0:
            totals[int(eid)] += actual

    return totals


def fetch_t4_sums(conn, year: int) -> Dict[int, Dict[str, float]]:
    cols = table_columns(conn, 'driver_payroll')
    t4_cols = [c for c in ("t4_box_14", "t4_box_16", "t4_box_18", "t4_box_22") if c in cols]
    if not t4_cols:
        return {}
    select_cols = ", ".join([f"COALESCE(SUM({c}),0) AS {c}" for c in t4_cols])
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute(
        f"""
        SELECT employee_id, {select_cols}
        FROM driver_payroll
        WHERE year=%s
        GROUP BY employee_id
        """,
        (year,),
    )
    out = {}
    for r in cur.fetchall():
        eid = r.get("employee_id")
        if eid is None:
            continue
        out[int(eid)] = {
            't4_box_14': float(r.get('t4_box_14', 0) or 0),
            't4_box_16': float(r.get('t4_box_16', 0) or 0),
            't4_box_18': float(r.get('t4_box_18', 0) or 0),
            't4_box_22': float(r.get('t4_box_22', 0) or 0),
        }
    cur.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="Generate pay statements including gratuity (configurable inclusion policy)")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--include-gratuity", choices=["all", "controlled", "none"], default="controlled")
    args = ap.parse_args()

    conn = get_db_connection()
    outdir = ensure_reports_dir()
    names = employee_names(conn)

    wage = fetch_wage_monthly(conn, args.year)
    t4_map = fetch_t4_sums(conn, args.year)

    detail_path = os.path.join(outdir, f"pay_plus_gratuity_{args.year}_detail.csv")
    summary_path = os.path.join(outdir, f"pay_plus_gratuity_{args.year}_summary.csv")
    with open(detail_path, 'w', newline='', encoding='utf-8') as fd, \
         open(summary_path, 'w', newline='', encoding='utf-8') as fs:
        wd = csv.writer(fd)
        ws = csv.writer(fs)
        wd.writerow(["employee_id", "full_name", "month", "wage_gross", "gratuity_included", "combined_gross", "cpp", "ei", "tax", "net"])
        ws.writerow(["employee_id", "full_name", "ytd_wage_gross", "ytd_gratuity", "ytd_combined_gross", "ytd_cpp", "ytd_ei", "ytd_tax", "ytd_net", "t4_box_14", "diff_box14"])

        all_eids = set(wage.keys())
        # Also include any drivers who only have gratuity
        # We will accumulate month by month
        for month in range(1, 13):
            g = fetch_gratuity_by_driver(conn, args.year, month, args.include_gratuity)
            all_eids.update(g.keys())
            for eid in sorted(all_eids):
                nm = names.get(eid, "")
                w = wage.get(eid, {})
                wvals = w.get(month, {"gross":0.0,"cpp":0.0,"ei":0.0,"tax":0.0,"net":0.0})
                gratuity = g.get(eid, 0.0)
                combined_gross = round(wvals['gross'] + gratuity, 2)
                wd.writerow([eid, nm, month, f"{wvals['gross']:.2f}", f"{gratuity:.2f}", f"{combined_gross:.2f}", f"{wvals['cpp']:.2f}", f"{wvals['ei']:.2f}", f"{wvals['tax']:.2f}", f"{wvals['net']:.2f}"])

        # YTD summary
        for eid in sorted(all_eids):
            nm = names.get(eid, "")
            ytd_wage_gross = sum(wage.get(eid, {}).get(m, {}).get('gross', 0.0) for m in range(1,13))
            ytd_cpp = sum(wage.get(eid, {}).get(m, {}).get('cpp', 0.0) for m in range(1,13))
            ytd_ei = sum(wage.get(eid, {}).get(m, {}).get('ei', 0.0) for m in range(1,13))
            ytd_tax = sum(wage.get(eid, {}).get(m, {}).get('tax', 0.0) for m in range(1,13))
            ytd_net = sum(wage.get(eid, {}).get(m, {}).get('net', 0.0) for m in range(1,13))
            # recompute gratuity month by month to avoid double counting
            ytd_grat = 0.0
            for month in range(1, 13):
                ytd_grat += fetch_gratuity_by_driver(conn, args.year, month, args.include_gratuity).get(eid, 0.0)
            ytd_combined = round(ytd_wage_gross + ytd_grat, 2)
            t4_14 = t4_map.get(eid, {}).get('t4_box_14', 0.0)
            diff14 = round(ytd_combined - t4_14, 2)
            ws.writerow([eid, nm, f"{ytd_wage_gross:.2f}", f"{ytd_grat:.2f}", f"{ytd_combined:.2f}", f"{ytd_cpp:.2f}", f"{ytd_ei:.2f}", f"{ytd_tax:.2f}", f"{ytd_net:.2f}", f"{t4_14:.2f}", f"{diff14:.2f}"])

    conn.close()
    print(f"Wrote: {detail_path}")
    print(f"Wrote: {summary_path}")


if __name__ == "__main__":
    main()
