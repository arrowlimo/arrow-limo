#!/usr/bin/env python3
"""
Generate CRA Audit Export and Summary (Standalone)
=================================================

Reads directly from PostgreSQL and produces two CSV files for a given date range:
- Full export: receipts detail with GST included/extracted fields
- Summary: category and vendor summaries with GST totals

Safe: Read-only operations. No database modifications.

Usage:
  python -X utf8 scripts/generate_cra_audit_export.py --year 2012
  python -X utf8 scripts/generate_cra_audit_export.py --start 2012-01-01 --end 2012-12-31

Outputs:
  exports/cra/<year>/cra_audit_export_<year>.csv
  exports/cra/<year>/cra_audit_summary_<year>.csv

Environment variables respected (defaults shown):
  DB_HOST=localhost
  DB_NAME=almsdata
  DB_USER=postgres
  DB_PASSWORD=***REDACTED***
"""
from __future__ import annotations

import os
import csv
import sys
import argparse
from datetime import date, datetime
import psycopg2
from psycopg2.extras import DictCursor


def get_dsn():
    return dict(
        host=os.environ.get("DB_HOST", "localhost"),
        database=os.environ.get("DB_NAME", "almsdata"),
        user=os.environ.get("DB_USER", "postgres"),
        password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
        port=int(os.environ.get("DB_PORT", "5432")),
    )


def parse_args():
    ap = argparse.ArgumentParser(description="Generate CRA audit export and summary from DB")
    ap.add_argument("--year", type=int, help="Convenience: set start/end to full calendar year")
    ap.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    ap.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    ap.add_argument("--outdir", type=str, default="exports/cra", help="Base output directory")
    return ap.parse_args()


def resolve_dates(args):
    if args.year:
        start = date(args.year, 1, 1)
        end = date(args.year, 12, 31)
    else:
        if not args.start or not args.end:
            raise SystemExit("Provide --year or both --start and --end")
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
    if start > end:
        raise SystemExit("Start date must be before end date")
    return start, end


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _get_columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def export_receipts(conn, start: date, end: date, out_path: str) -> int:
    """Export detailed receipts for date range. Returns row count.

    Defensive: builds SELECT based on actual schema present.
    """
    cols = _get_columns(conn, "receipts")

    # Map desired fields to available columns with fallbacks
    field_map = {
        "id": next((c for c in ("receipt_id", "id") if c in cols), None),
        "date": next((c for c in ("receipt_date", "date", "transaction_date") if c in cols), None),
        "vendor": next((c for c in ("vendor_name", "vendor", "payee") if c in cols), None),
        "category": "category" if "category" in cols else None,
        "gross": next((c for c in ("gross_amount", "amount", "total", "payment_amount") if c in cols), None),
        "gst": next((c for c in ("gst_amount", "tax_amount", "gst") if c in cols), None),
        "net": next((c for c in ("net_amount",) if c in cols), None),
        "tax_rate": "tax_rate" if "tax_rate" in cols else None,
        "is_taxable": "is_taxable" if "is_taxable" in cols else None,
        "description": next((c for c in ("description", "notes", "memo") if c in cols), None),
        "created_at": "created_at" if "created_at" in cols else None,
        "updated_at": "updated_at" if "updated_at" in cols else None,
        "created_from_banking": "created_from_banking" if "created_from_banking" in cols else None,
    }

    select_parts = []
    order_keys = []

    if field_map["id"]:
        select_parts.append(f"{field_map['id']} AS receipt_id")
        order_keys.append(field_map["id"])
    else:
        select_parts.append("NULL::int AS receipt_id")

    if field_map["date"]:
        select_parts.append(f"{field_map['date']} AS receipt_date")
        order_keys.append(field_map["date"])
    else:
        select_parts.append("NULL::date AS receipt_date")

    if field_map["vendor"]:
        select_parts.append(f"{field_map['vendor']} AS vendor_name")
        order_keys.append(field_map["vendor"])
    else:
        select_parts.append("''::text AS vendor_name")

    if field_map["category"]:
        select_parts.append("COALESCE(category,'') AS category")
    else:
        select_parts.append("''::text AS category")

    # Amounts
    if field_map["gross"]:
        select_parts.append(f"COALESCE({field_map['gross']},0)::numeric(12,2) AS gross_amount")
    else:
        select_parts.append("0::numeric(12,2) AS gross_amount")

    if field_map["gst"]:
        select_parts.append(f"COALESCE({field_map['gst']},0)::numeric(12,2) AS gst_amount")
    else:
        select_parts.append("0::numeric(12,2) AS gst_amount")

    if field_map["net"]:
        select_parts.append(f"COALESCE({field_map['net']},0)::numeric(12,2) AS net_amount")
    else:
        # Compute if possible
        if field_map["gross"] and field_map["gst"]:
            select_parts.append(
                f"(COALESCE({field_map['gross']},0) - COALESCE({field_map['gst']},0))::numeric(12,2) AS net_amount"
            )
        else:
            select_parts.append("0::numeric(12,2) AS net_amount")

    if field_map["tax_rate"]:
        select_parts.append("COALESCE(tax_rate,0)::numeric(5,4) AS tax_rate")
    else:
        select_parts.append("0::numeric(5,4) AS tax_rate")

    if field_map["is_taxable"]:
        select_parts.append("COALESCE(is_taxable,true) AS is_taxable")
    else:
        select_parts.append("TRUE AS is_taxable")

    if field_map["description"]:
        select_parts.append(f"COALESCE({field_map['description']},'') AS description")
    else:
        select_parts.append("''::text AS description")

    if field_map["created_at"]:
        select_parts.append("created_at")
    else:
        select_parts.append("NULL::timestamp AS created_at")

    if field_map["updated_at"]:
        select_parts.append("updated_at")
    else:
        select_parts.append("NULL::timestamp AS updated_at")

    if field_map["created_from_banking"]:
        select_parts.append("COALESCE(created_from_banking,false) AS created_from_banking")
    else:
        select_parts.append("FALSE AS created_from_banking")

    # Date filter column
    date_col = field_map["date"] or "receipt_date"  # may be NULL; filter will then return 0 rows

    query = f"""
        SELECT 
            {',\n            '.join(select_parts)}
        FROM receipts
        WHERE {date_col} BETWEEN %s AND %s
        ORDER BY {', '.join([k for k in order_keys if k])}
    """

    with conn.cursor(cursor_factory=DictCursor) as cur, open(out_path, "w", newline="", encoding="utf-8") as f:
        try:
            cur.execute(query, (start, end))
        except Exception as e:
            # Fallback: if date_col missing entirely, select without WHERE to avoid hard fail
            if "column" in str(e).lower() and "does not exist" in str(e).lower():
                cur.execute(f"SELECT {', '.join(select_parts)} FROM receipts")
            else:
                raise
        rows = cur.fetchall()
        # Write CSV
        fieldnames = [
            "receipt_id", "receipt_date", "vendor_name", "category", "gross_amount",
            "gst_amount", "net_amount", "tax_rate", "is_taxable", "description",
            "created_at", "updated_at", "created_from_banking",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
        return len(rows)


def export_summary(conn, start: date, end: date, out_path: str) -> dict:
    """Export category and vendor summaries. Returns counts."""
    results = {
        "by_category_rows": 0,
        "by_vendor_rows": 0,
        "totals": {},
    }

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Header block
        writer.writerow(["CRA AUDIT SUMMARY"])
        writer.writerow(["Period", f"{start} to {end}"])
        writer.writerow([])

        # Totals
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    COALESCE(SUM(gross_amount),0)::numeric(14,2) AS gross_total,
                    COALESCE(SUM(gst_amount),0)::numeric(14,2) AS gst_total,
                    COALESCE(SUM(net_amount),0)::numeric(14,2) AS net_total,
                    COUNT(*) AS receipt_count
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                """,
                (start, end),
            )
            gross_total, gst_total, net_total, receipt_count = cur.fetchone()
            results["totals"] = dict(
                gross_total=str(gross_total),
                gst_total=str(gst_total),
                net_total=str(net_total),
                receipt_count=int(receipt_count),
            )
            writer.writerow(["TOTALS", "Gross", gross_total, "GST", gst_total, "Net", net_total, "Receipts", receipt_count])
            writer.writerow([])

        # By category
        writer.writerow(["BY CATEGORY"])
        writer.writerow(["category", "receipts", "gross_total", "gst_total", "net_total"])
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    COALESCE(category, '') AS category,
                    COUNT(*) AS receipts,
                    COALESCE(SUM(gross_amount),0)::numeric(14,2) AS gross_total,
                    COALESCE(SUM(gst_amount),0)::numeric(14,2) AS gst_total,
                    COALESCE(SUM(net_amount),0)::numeric(14,2) AS net_total
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                GROUP BY 1
                ORDER BY 2 DESC
                """,
                (start, end),
            )
            rows = cur.fetchall()
            for row in rows:
                writer.writerow([row[0], int(row[1]), row[2], row[3], row[4]])
            results["by_category_rows"] = len(rows)
        writer.writerow([])

        # By vendor
        writer.writerow(["BY VENDOR"])
        writer.writerow(["vendor_name", "receipts", "gross_total", "gst_total", "net_total"])
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    COALESCE(vendor_name, '') AS vendor_name,
                    COUNT(*) AS receipts,
                    COALESCE(SUM(gross_amount),0)::numeric(14,2) AS gross_total,
                    COALESCE(SUM(gst_amount),0)::numeric(14,2) AS gst_total,
                    COALESCE(SUM(net_amount),0)::numeric(14,2) AS net_total
                FROM receipts
                WHERE receipt_date BETWEEN %s AND %s
                GROUP BY 1
                ORDER BY 2 DESC
                """,
                (start, end),
            )
            rows = cur.fetchall()
            for row in rows:
                writer.writerow([row[0], int(row[1]), row[2], row[3], row[4]])
            results["by_vendor_rows"] = len(rows)

    return results


def main():
    args = parse_args()
    start, end = resolve_dates(args)

    # Output paths
    year_folder = str(start.year) if start.year == end.year else f"{start.year}-{end.year}"
    outdir = os.path.join(args.outdir, year_folder)
    ensure_dir(outdir)

    export_path = os.path.join(outdir, f"cra_audit_export_{year_folder}.csv")
    summary_path = os.path.join(outdir, f"cra_audit_summary_{year_folder}.csv")

    dsn = get_dsn()
    print("Connecting to PostgreSQL...", dsn["host"], dsn["database"])
    try:
        with psycopg2.connect(**dsn) as conn:
            # Full export
            print(f"\nGenerating full export: {export_path}")
            count = export_receipts(conn, start, end, export_path)
            print(f"  [OK] Wrote {count} receipt rows")

            # Summary
            print(f"\nGenerating summary: {summary_path}")
            res = export_summary(conn, start, end, summary_path)
            print(
                "  [OK] Summary rows:",
                {k: v for k, v in res.items() if not isinstance(v, dict)}
            )
            print("  [OK] Totals:", res.get("totals"))

            print("\n🎉 CRA audit export complete.")
            print("   Files:")
            print("   -", export_path)
            print("   -", summary_path)
    except Exception as e:
        print("[FAIL] Error generating CRA audit export:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
