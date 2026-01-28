#!/usr/bin/env python3
"""
QuickBooks Lists Delta Report (ACCNT vs chart_of_accounts)
---------------------------------------------------------
Reads a QuickBooks IIF lists export, extracts ACCNT records (account name/type/number),
compares them to the database chart_of_accounts, and reports ONLY what's missing.

Outputs a Markdown report at reports/qb_list_delta.md and prints a short summary.

Safety/assumptions:
- Uses api.get_db_connection() to respect DB_* env vars.
- Defensively introspects chart_of_accounts columns to handle schema variants.
- Case-insensitive name comparison; trims whitespace.
- Treats account_number vs account_code as interchangeable "number" field.
"""
import os
import sys
import pathlib
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Set

# Add repo root to path and import DB helper
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api import get_db_connection  # type: ignore

IIF_PATH = pathlib.Path(r"l:\\limo\\qbb\\qbw\\limousine.IIF")
REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(exist_ok=True)
REPORT_PATH = REPORT_DIR / "qb_list_delta.md"

# Minimal IIF parser for ACCNT sections

def parse_iif_accounts(iif_path: pathlib.Path) -> List[Dict[str, str]]:
    """Parse IIF and return list of ACCNT dicts with keys from section header."""
    accounts: List[Dict[str, str]] = []
    current_header: Optional[List[str]] = None
    try:
        with iif_path.open("r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                line = raw.rstrip("\n\r")
                if not line:
                    continue
                parts = line.split("\t")
                if not parts:
                    continue
                tag = parts[0].strip()
                # Header for ACCNT section
                if tag.startswith("!ACCNT"):
                    # The rest of parts are column labels
                    current_header = [p.strip().upper() for p in parts[1:]]
                    continue
                # Data row in ACCNT section
                if tag == "ACCNT" and current_header:
                    row_vals = parts[1:]
                    # Pad/truncate to header length
                    if len(row_vals) < len(current_header):
                        row_vals = row_vals + [""] * (len(current_header) - len(row_vals))
                    elif len(row_vals) > len(current_header):
                        row_vals = row_vals[:len(current_header)]
                    row = {current_header[i]: (row_vals[i] or "").strip() for i in range(len(current_header))}
                    accounts.append(row)
    except FileNotFoundError:
        print(f"IIF not found: {iif_path}")
    return accounts


def normalize(s: Optional[str]) -> str:
    return (s or "").strip().lower()


def extract_name_number(row: Dict[str, str]) -> Tuple[str, str, str]:
    """Return (name, number, accnttype) from an IIF ACCNT row with tolerant keys."""
    # Common IIF columns seen: NAME, ACCNTTYPE, DESC, ACCNTNUM, BANKNUM
    name = row.get("NAME") or row.get("ACCNTNAME") or row.get("FULLNAME") or ""
    accnttype = row.get("ACCNTTYPE") or row.get("TYPE") or ""
    number = row.get("ACCNTNUM") or row.get("NUMBER") or row.get("ACCNTNUMBER") or row.get("BANKNUM") or ""
    return name.strip(), number.strip(), accnttype.strip()


def get_chart_columns(cur) -> Dict[str, bool]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='chart_of_accounts'
        """
    )
    cols = {r[0].lower(): True for r in cur.fetchall()}
    return cols


def load_chart_accounts(cur, cols: Dict[str, bool]) -> List[Tuple[str, str, str]]:
    """Return list of (name, number, type) from chart_of_accounts with defensive selects."""
    # Prefer account_name; fallback to name
    name_col = "account_name" if cols.get("account_name") else ("name" if cols.get("name") else None)
    # Prefer account_number; fallback to account_code; else empty string
    number_col = "account_number" if cols.get("account_number") else ("account_code" if cols.get("account_code") else None)
    type_col = "account_type" if cols.get("account_type") else None

    select_cols = []
    if name_col:
        select_cols.append(name_col)
    else:
        select_cols.append("'' AS account_name")
    if number_col:
        select_cols.append(number_col)
    else:
        select_cols.append("'' AS account_number")
    if type_col:
        select_cols.append(type_col)
    else:
        select_cols.append("'' AS account_type")

    sql = f"SELECT {', '.join(select_cols)} FROM chart_of_accounts"
    cur.execute(sql)
    rows = cur.fetchall()

    out: List[Tuple[str, str, str]] = []
    for r in rows:
        n = r[0] or ""
        num = r[1] or ""
        t = r[2] or ""
        out.append((str(n).strip(), str(num).strip(), str(t).strip()))
    return out


def main():
    if not IIF_PATH.exists():
        print(f"[FAIL] IIF file not found: {IIF_PATH}")
        sys.exit(1)

    iif_accounts = parse_iif_accounts(IIF_PATH)
    if not iif_accounts:
        print("[WARN] No ACCNT records found in IIF (lists file may be different than expected).")

    iif_by_name: Dict[str, Tuple[str, str]] = {}
    iif_by_number: Dict[str, Tuple[str, str]] = {}

    for row in iif_accounts:
        name, number, accnttype = extract_name_number(row)
        if name:
            iif_by_name[normalize(name)] = (name, accnttype)
        if number:
            iif_by_number[number.strip()] = (name or "", accnttype)

    # Connect to DB
    conn = get_db_connection()
    cur = conn.cursor()

    # Check staging presence
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='public' AND table_name='qb_accounts_staging'
        """
    )
    has_staging = cur.fetchone()[0] > 0
    staging_count = None
    if has_staging:
        cur.execute("SELECT COUNT(*) FROM qb_accounts_staging")
        staging_count = cur.fetchone()[0]

    # Load chart accounts with defensive columns
    chart_cols = get_chart_columns(cur)
    chart_rows = load_chart_accounts(cur, chart_cols)

    chart_by_name: Set[str] = set()
    chart_by_number: Set[str] = set()

    for name, number, atype in chart_rows:
        if name:
            chart_by_name.add(normalize(name))
        if number:
            chart_by_number.add(number.strip())

    # Deltas
    missing_names = [v for key, v in iif_by_name.items() if key not in chart_by_name]
    missing_numbers = [ (num, v[0], v[1]) for num, v in iif_by_number.items() if num not in chart_by_number ]

    # Write report
    lines: List[str] = []
    lines.append("# QuickBooks Lists Delta (ACCNT → chart_of_accounts)\n")
    lines.append(f"Source IIF: `{IIF_PATH}`\n")
    lines.append(f"Total ACCNT in IIF: {len(iif_accounts)}")
    lines.append(f"Total accounts in chart_of_accounts: {len(chart_rows)}\n")

    if has_staging:
        lines.append(f"qb_accounts_staging present: yes (rows: {staging_count})\n")
    else:
        lines.append("qb_accounts_staging present: no\n")

    lines.append("## Missing by Name (present in IIF, not in chart_of_accounts)\n")
    if missing_names:
        for name, accnttype in sorted(missing_names, key=lambda x: x[0].lower()):
            lines.append(f"- {name} ({accnttype})")
    else:
        lines.append("- None")

    lines.append("\n## Missing by Number (present in IIF, not in chart_of_accounts)\n")
    if missing_numbers:
        for num, name, accnttype in sorted(missing_numbers, key=lambda x: (x[0], x[1].lower())):
            lines.append(f"- {num}: {name} ({accnttype})")
    else:
        lines.append("- None")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")

    # Print concise summary
    print("\n=== Quick Summary ===")
    print(f"IIF ACCNT records: {len(iif_accounts)}")
    print(f"chart_of_accounts records: {len(chart_rows)}")
    print(f"Missing by name: {len(missing_names)}")
    print(f"Missing by number: {len(missing_numbers)}")
    if has_staging:
        print(f"qb_accounts_staging rows: {staging_count}")
    print(f"Report written: {REPORT_PATH}")

    cur.close(); conn.close()

if __name__ == "__main__":
    main()
