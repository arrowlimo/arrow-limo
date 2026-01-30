import os
import re
import sys
import json
from collections import defaultdict, Counter
from datetime import datetime

import psycopg2


def env(name, default=None):
    return os.environ.get(name, default)


def get_db_connection():
    return psycopg2.connect(
        host=env("DB_HOST", "localhost"),
        dbname=env("DB_NAME", "almsdata"),
        user=env("DB_USER", "postgres"),
        password=env("DB_PASSWORD", "***REDACTED***"),
    )


YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")


READABLE_EXT = {".csv", ".txt", ".zip"}  # xlsx requires deps; pdf is not program-readable here
QB_EXT = {".qbb", ".qbw", ".qbm"}
INFO_EXT = {".pdf", ".xlsx"}


def extract_years_from_name(name):
    years = set()
    for m in YEAR_RE.finditer(name):
        y = int(m.group(1))
        if 1980 <= y <= 2035:
            years.add(y)
    return years


def scan_dir(base_dir):
    inventory = []
    ext_counts = Counter()
    years_hint = Counter()

    for root, dirs, files in os.walk(base_dir):
        for fn in files:
            path = os.path.join(root, fn)
            ext = os.path.splitext(fn)[1].lower()
            ext_counts[ext] += 1
            yrs = extract_years_from_name(fn) | extract_years_from_name(root)
            for y in yrs:
                years_hint[y] += 1
            inventory.append({
                "path": path,
                "ext": ext,
                "years": sorted(list(yrs)),
                "readable": ext in READABLE_EXT,
                "qb_backup": ext in QB_EXT,
                "info_only": ext in INFO_EXT,
            })
    return inventory, ext_counts, years_hint


def db_year_presence(conn, years):
    cur = conn.cursor()
    presence = {}

    # Discover available public tables
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema='public'
        """
    )
    tables = {r[0] for r in cur.fetchall()}

    # banking_transactions by year (if exists)
    if 'banking_transactions' in tables:
        cur.execute("SELECT MIN(transaction_date), MAX(transaction_date) FROM banking_transactions")
        rng = cur.fetchone()
        presence["banking_range"] = {
            "min": str(rng[0]) if rng and rng[0] else None,
            "max": str(rng[1]) if rng and rng[1] else None,
        }
    else:
        presence["banking_range"] = {"min": None, "max": None}

    for y in sorted(years):
        start = f"{y}-01-01"
        end = f"{y}-12-31"
        year_info = {}

        # Banking
        if 'banking_transactions' in tables:
            cur.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(COALESCE(debit_amount,0)),0), COALESCE(SUM(COALESCE(credit_amount,0)),0)
                FROM banking_transactions
                WHERE transaction_date >= %s AND transaction_date <= %s
                """,
                (start, end),
            )
            r = cur.fetchone()
            year_info["banking"] = {
                "count": int(r[0] or 0),
                "debits": float(r[1] or 0),
                "credits": float(r[2] or 0),
            }
        else:
            year_info["banking"] = {"count": 0, "debits": 0.0, "credits": 0.0}

        # Receipts
        if 'receipts' in tables:
            cur.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(COALESCE(gross_amount,0)),0)
                FROM receipts
                WHERE receipt_date >= %s AND receipt_date <= %s
                """,
                (start, end),
            )
            r = cur.fetchone()
            year_info["receipts"] = {
                "count": int(r[0] or 0),
                "gross_total": float(r[1] or 0),
            }
        else:
            year_info["receipts"] = {"count": 0, "gross_total": 0.0}

        # GL
        if 'unified_general_ledger' in tables:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM unified_general_ledger
                WHERE transaction_date >= %s AND transaction_date <= %s
                """,
                (start, end),
            )
            r = cur.fetchone()
            year_info["unified_gl"] = {"count": int(r[0] or 0)}
        else:
            year_info["unified_gl"] = {"count": 0}

        presence[y] = year_info

    return presence


def write_report(base_dir, inventory, ext_counts, years_hint, presence):
    out_dir = os.path.join("exports", "audit")
    os.makedirs(out_dir, exist_ok=True)
    report_path = os.path.join(out_dir, "qb_dir_scan_report.md")

    lines = []
    lines.append(f"# QuickBooks Folder Scan Report")
    lines.append("")
    lines.append(f"Scanned: {base_dir}")
    lines.append("")
    lines.append("## File extensions summary")
    lines.append("")
    for ext, cnt in sorted(ext_counts.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- {ext or '(no ext)'}: {cnt}")
    lines.append("")

    if years_hint:
        lines.append("## Years detected from filenames/folders")
        lines.append("")
        for y, cnt in sorted(years_hint.items()):
            lines.append(f"- {y}: {cnt} files")
        lines.append("")

    lines.append("## Database presence by year")
    lines.append("")
    br = presence.get("banking_range", {})
    lines.append(f"Banking date range: {br.get('min')} - {br.get('max')}")
    for y in sorted(k for k in presence.keys() if isinstance(k, int)):
        info = presence[y]
        lines.append("")
        lines.append(f"### {y}")
        lines.append(f"- Banking: {info['banking']['count']} txns, debits ${info['banking']['debits']:,.2f}, credits ${info['banking']['credits']:,.2f}")
        lines.append(f"- Receipts: {info['receipts']['count']} receipts, gross ${info['receipts']['gross_total']:,.2f}")
        lines.append(f"- Unified GL: {info['unified_gl']['count']} rows")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n[OK] Wrote report: {report_path}")
    return report_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Scan a QuickBooks folder and compare to almsdata coverage")
    parser.add_argument("--dir", required=True, help="Directory to scan (e.g., L:\\qbb\\qbw)")
    args = parser.parse_args()

    base_dir = args.dir
    if not os.path.isdir(base_dir):
        print(f"ERROR: Directory not found: {base_dir}")
        sys.exit(2)

    print(f"Scanning {base_dir} ...")
    inventory, ext_counts, years_hint = scan_dir(base_dir)

    years = set(years_hint.keys())
    if not years:
        # Default to 2012-2015 since that's what we care about right now
        years = {2012, 2013, 2014, 2015}

    conn = get_db_connection()
    try:
        presence = db_year_presence(conn, years)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    report_path = write_report(base_dir, inventory, ext_counts, years_hint, presence)
    print("\nSummary:")
    print(f" - Files scanned: {len(inventory)}")
    print(f" - Extensions found: {len(ext_counts)}")
    print(f" - Years hinted by names: {sorted(years_hint.keys()) if years_hint else '(none)'}")
    print(f" - Report: {report_path}")


if __name__ == "__main__":
    main()
