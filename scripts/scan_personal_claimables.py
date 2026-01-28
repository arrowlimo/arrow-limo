"""
Scan receipts for likely personal claimable expenses and compute taxable owner benefit (incl. GST).

What it does
- Loads taxonomy from scripts/claimable_personal_expenses.json
- Queries receipts in a date range (default: current year) from Postgres almsdata
- Uses keyword matching with exclusions to flag likely personal items
- Computes benefit = total paid including GST (gross), with GST fallback if missing
- Outputs a CSV with details and prints per-category and grand totals

Notes
- If the period has no receipts (e.g., 2025), exits cleanly with a note.
- This is guidance-only. Final eligibility depends on CRA rules and documentation.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import DictCursor


DEFAULT_GST_RATE = 0.05  # Alberta GST (no PST). Used as fallback when GST not stored.


def get_db_connection():
    return psycopg2.connect(
        dbname=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", os.environ.get("PGPASSWORD", "***REMOVED***")),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5432"),
    )


@dataclass
class TaxonomyItem:
    code: str
    name: str
    keywords: List[str]
    exclude_keywords: List[str]
    active_years: List[int]


def load_taxonomy(path: str) -> List[TaxonomyItem]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: List[TaxonomyItem] = []
    for item in data.get("categories", []):
        out.append(
            TaxonomyItem(
                code=item.get("code", "UNKNOWN"),
                name=item.get("name", item.get("code", "UNKNOWN")),
                keywords=[k.lower() for k in item.get("keywords", [])],
                exclude_keywords=[k.lower() for k in item.get("exclude_keywords", [])],
                active_years=item.get("active_years", []),
            )
        )
    return out


def normalize_text(*parts: Optional[str]) -> str:
    text = " ".join([p or "" for p in parts])
    text = text.lower()
    # Keep letters, numbers, spaces
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def match_category(taxonomy: List[TaxonomyItem], text: str, year: int) -> Tuple[Optional[TaxonomyItem], List[str], List[str]]:
    hits: List[str] = []
    excludes: List[str] = []
    best: Optional[TaxonomyItem] = None
    best_score = -1
    for t in taxonomy:
        if t.active_years and year not in t.active_years:
            continue
        local_hits = [k for k in t.keywords if k and k in text]
        if not local_hits:
            continue
        local_excl = [k for k in t.exclude_keywords if k and k in text]
        # score = number of keyword hits minus exclusions
        score = len(local_hits) - (2 * len(local_excl))
        if score > best_score:
            best_score = score
            best = t
            hits = local_hits
            excludes = local_excl
    return best, hits, excludes


def compute_benefit(gross_amount: Optional[float], gst_amount: Optional[float], assume_gst_rate: float) -> Tuple[float, float, float]:
    """
    Returns (benefit_total_incl_gst, gst_component, net_component)
    - If gross present: benefit = gross (total paid incl. GST)
    - gst_component = gst_amount if present; else derive from gross: gross * (rate/(1+rate))
    - net_component = benefit - gst_component
    """
    gross = float(gross_amount or 0.0)
    if gross <= 0:
        return 0.0, 0.0, 0.0
    if gst_amount is not None and float(gst_amount) > 0:
        gst = float(gst_amount)
    else:
        gst = round(gross * (assume_gst_rate / (1.0 + assume_gst_rate)), 2)
    net = round(gross - gst, 2)
    return round(gross, 2), gst, net


def daterange_from_args(args: argparse.Namespace) -> Tuple[dt.date, dt.date]:
    if args.start_date and args.end_date:
        start = dt.date.fromisoformat(args.start_date)
        end = dt.date.fromisoformat(args.end_date)
        # Make end exclusive by adding one day
        return start, end + dt.timedelta(days=1)
    year = args.year or dt.date.today().year
    start = dt.date(year, 1, 1)
    end = dt.date(year + 1, 1, 1)  # exclusive
    return start, end


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scan receipts for personal claimables and owner benefit (incl. GST)")
    p.add_argument("--year", type=int, help="Tax year to scan (default: current year)")
    p.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    p.add_argument("--end-date", help="End date inclusive (YYYY-MM-DD)")
    p.add_argument("--min-amount", type=float, default=0.0, help="Minimum gross amount to consider (default 0)")
    p.add_argument("--assume-gst-rate", type=float, default=DEFAULT_GST_RATE, help="GST rate fallback when GST not stored (default 0.05)")
    p.add_argument("--taxonomy", default=os.path.join(os.path.dirname(__file__), "claimable_personal_expenses.json"), help="Path to taxonomy JSON")
    p.add_argument("--owner", default="Paul", help="Owner name for reporting (default: Paul)")
    p.add_argument("--last-month", dest="last_month", action="store_true", help="Scan the last full calendar month (overrides --year if provided)")
    p.add_argument("--output", help="Output CSV path (default: reports/personal_benefits_<year>.csv)")
    p.add_argument("--limit", type=int, help="Limit number of receipts for quick tests")
    p.add_argument("--verbose", action="store_true", help="Print matched rows as they are found")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    # Support --last-month convenience
    if getattr(args, 'last_month', False):
        today = dt.date.today()
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - dt.timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        start_date, end_exclusive = last_month_start, last_month_end + dt.timedelta(days=1)
        # Set year for default filename/report grouping
        if not args.year:
            args.year = last_month_start.year
    else:
        start_date, end_exclusive = daterange_from_args(args)
    scan_year = (args.year or start_date.year)

    taxonomy_path = args.taxonomy
    if not os.path.isabs(taxonomy_path):
        taxonomy_path = os.path.abspath(taxonomy_path)
    taxonomy = load_taxonomy(taxonomy_path)

    # Prepare output file path
    if args.output:
        out_path = args.output
    else:
        reports_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "reports"))
        os.makedirs(reports_dir, exist_ok=True)
        # If this is a custom range not covering a whole year, include month in filename
        if getattr(args, 'last_month', False):
            out_path = os.path.join(reports_dir, f"personal_benefits_{start_date.year}_{start_date.month:02d}.csv")
        elif args.start_date and args.end_date:
            out_path = os.path.join(reports_dir, f"personal_benefits_{start_date}_{(end_exclusive - dt.timedelta(days=1))}.csv")
        else:
            out_path = os.path.join(reports_dir, f"personal_benefits_{scan_year}.csv")

    # Query receipts
    sql = (
        "SELECT id, receipt_date, vendor_name, "
        "       COALESCE(description, comment, '') AS description, "
        "       category, gross_amount, gst_amount "
        "  FROM receipts "
        " WHERE receipt_date >= %s AND receipt_date < %s "
        "   AND COALESCE(gross_amount,0) > 0 "
        " ORDER BY receipt_date ASC, id ASC"
    )

    rows: List[Dict[str, Any]] = []
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                params: List[Any] = [start_date, end_exclusive]
                if args.limit:
                    sql_limited = sql + " LIMIT %s"
                    params.append(args.limit)
                    cur.execute(sql_limited, params)
                else:
                    cur.execute(sql, params)
                for r in cur.fetchall():
                    rows.append(dict(r))
    except Exception as e:
        print(f"Error querying receipts: {e}")
        return 2

    if not rows:
        # Graceful no-data handling (e.g., 2025 empty)
        period = f"{start_date} to {(end_exclusive - dt.timedelta(days=1))}"
        print(f"No receipts found in period {period}. Nothing to report.")
        # Still create an empty CSV with header for consistency
        write_csv(out_path, [])
        print(f"Wrote empty report: {out_path}")
        return 0

    # Process
    matches: List[Dict[str, Any]] = []
    totals_by_category: Dict[str, float] = {}
    totals_gst: Dict[str, float] = {}
    grand_total = 0.0
    grand_gst = 0.0

    for r in rows:
        rid = r.get("id")
        rdate = r.get("receipt_date")
        vendor = r.get("vendor_name")
        desc = r.get("description")
        cat = r.get("category")
        gross = safe_float(r.get("gross_amount"))
        gst = safe_optional_float(r.get("gst_amount"))

        # Skip small amounts if requested
        if args.min_amount and (gross or 0.0) < args.min_amount:
            continue

        norm = normalize_text(vendor, desc, cat)
        titem, hits, excl = match_category(taxonomy, norm, year=rdate.year if isinstance(rdate, dt.date) else scan_year)
        if not titem:
            continue

        benefit_total, gst_comp, net_comp = compute_benefit(gross, gst, args.assume_gst_rate)
        if benefit_total <= 0:
            continue

        totals_by_category[titem.code] = round(totals_by_category.get(titem.code, 0.0) + benefit_total, 2)
        totals_gst[titem.code] = round(totals_gst.get(titem.code, 0.0) + gst_comp, 2)
        grand_total = round(grand_total + benefit_total, 2)
        grand_gst = round(grand_gst + gst_comp, 2)

        row_out = {
            "receipt_id": rid,
            "receipt_date": rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate),
            "vendor": vendor or "",
            "description": desc or "",
            "db_category": cat or "",
            "detected_code": titem.code,
            "detected_name": titem.name,
            "matched_keywords": ",".join(hits),
            "exclusion_hits": ",".join(excl),
            "gross_amount": f"{gross:.2f}" if gross is not None else "",
            "gst_amount": f"{(gst or 0.0):.2f}",
            "benefit_total_incl_gst": f"{benefit_total:.2f}",
            "benefit_gst_component": f"{gst_comp:.2f}",
            "benefit_net_component": f"{net_comp:.2f}",
            "owner": args.owner,
            "tax_year": rdate.year if isinstance(rdate, dt.date) else scan_year,
        }
        matches.append(row_out)

        if getattr(args, "verbose", False):
            print(f"[{row_out['receipt_date']}] {row_out['vendor'][:24]:24} -> {titem.code} ${benefit_total:.2f}")

    # Output
    write_csv(out_path, matches)

    # Summary
    print(f"\nOwner taxable benefits for {args.owner} ({start_date} to {(end_exclusive - dt.timedelta(days=1))})")
    for code, total in sorted(totals_by_category.items(), key=lambda kv: kv[0]):
        gst_sum = totals_gst.get(code, 0.0)
        print(f"  {code:18}  total=${total:10.2f}   gst=${gst_sum:8.2f}")
    print(f"-- Grand total (incl. GST) = ${grand_total:,.2f} | GST component = ${grand_gst:,.2f}")
    print(f"Wrote: {out_path}")
    return 0


def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def safe_optional_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        f = float(x)
        return f
    except Exception:
        return None


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "receipt_id",
        "receipt_date",
        "vendor",
        "description",
        "db_category",
        "detected_code",
        "detected_name",
        "matched_keywords",
        "exclusion_hits",
        "gross_amount",
        "gst_amount",
        "benefit_total_incl_gst",
        "benefit_gst_component",
        "benefit_net_component",
        "owner",
        "tax_year",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    sys.exit(main())
