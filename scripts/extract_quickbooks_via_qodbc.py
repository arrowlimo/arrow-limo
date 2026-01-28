#!/usr/bin/env python3
"""
QuickBooks Extractor via QODBC
==============================

Extract core QuickBooks entities and transaction data using QODBC.

Requirements:
- QuickBooks Desktop installed and the target company file open
- QODBC driver installed and authorized for the company file
- Python `pyodbc` installed in this environment

Usage examples:
- Use default DSN (e.g., "QuickBooks Data"):
    python scripts/extract_quickbooks_via_qodbc.py --dsn "QuickBooks Data"

- Use a file DSN:
    python scripts/extract_quickbooks_via_qodbc.py --filedsn "L:\\limo\\quickbooks\\oldArrow Limo Services.QBW.DSN"

- Direct driver + company file path (if DSN not configured):
    python scripts/extract_quickbooks_via_qodbc.py --company "L:\\limo\\quickbooks\\oldArrow Limo Services.QBW"

You can limit by date range (when supported by the view):
    --since 2007-01-01 --until 2012-12-31

Outputs are written to: L:\\limo\\docs\\qbw_extracts\\YYYYMMDD_HHMMSS\\
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Iterable, Optional

try:
    import pyodbc  # type: ignore
except Exception as e:  # pragma: no cover
    print("[FAIL] pyodbc is not available. Please install it in this environment.")
    print(f"Detail: {e}")
    sys.exit(1)


DEFAULT_ENTITIES = [
    "Account",
    "Customer",
    "Vendor",
    "Item",
]

# Txn/TxnLine provide a comprehensive, normalized view across transaction types
DEFAULT_TXN_VIEWS = [
    "Txn",
    "TxnLine",
]


def build_connection_string(dsn: Optional[str], filedsn: Optional[str], company: Optional[str]) -> str:
    if dsn:
        return f"DSN={dsn};READONLY=YES;"
    if filedsn:
        # FILEDSN points to a .dsn file created by QODBC
        return f"FILEDSN={filedsn};READONLY=YES;"
    if company:
        # Direct driver string. Driver name may vary by install; this is common.
        # If your driver name differs, pass --dsn instead.
        return (
            f"Driver={{QODBC Driver for QuickBooks}};"
            f"DFQ={company};OpenMode=ReadOnly;Optimistic=No;"
        )
    # Fallback: try the standard system DSN name
    return "DSN=QuickBooks Data;READONLY=YES;"


def ensure_output_dir(base_out: Optional[str]) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = Path(base_out) if base_out else Path("l:/limo/docs/qbw_extracts")
    out_dir = base / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def write_csv(cursor: pyodbc.Cursor, out_path: Path, limit: Optional[int] = None) -> int:
    cols = [col[0] for col in cursor.description]
    count = 0
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in cursor:
            w.writerow(row)
            count += 1
            if limit is not None and count >= limit:
                break
    return count


def query_with_date_filters(view: str, since: Optional[str], until: Optional[str]) -> str:
    # Not all views support TxnDate. Txn/TxnLine do; Account/Customer/Vendor/Item do not.
    date_filter = ""
    if view.lower() in {"txn", "txnline", "journalentry", "journalentryline"}:
        clauses = []
        if since:
            clauses.append(f"TxnDate >= {{d '{since}'}}")
        if until:
            clauses.append(f"TxnDate <= {{d '{until}'}}")
        if clauses:
            date_filter = " WHERE " + " AND ".join(clauses)
    return f"SELECT * FROM {view}{date_filter}"


def extract_views(conn: pyodbc.Connection, views: Iterable[str], out_dir: Path, since: Optional[str], until: Optional[str], limit: Optional[int]) -> dict[str, int]:
    results: dict[str, int] = {}
    for view in views:
        try:
            sql = query_with_date_filters(view, since, until)
            print(f"→ Extracting {view} ...")
            cursor = conn.cursor()
            cursor.execute(sql)
            out_path = out_dir / f"{view}.csv"
            rows = write_csv(cursor, out_path, limit=limit)
            results[view] = rows
            print(f"  Saved {rows} rows to {out_path}")
        except pyodbc.Error as e:
            print(f"  [WARN]  Skipped {view}: {e}")
        except Exception as e:  # pragma: no cover
            print(f"  [WARN]  Skipped {view}: {e}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Extract QuickBooks data via QODBC")
    conn_group = parser.add_mutually_exclusive_group()
    conn_group.add_argument("--dsn", help="ODBC DSN name (e.g., 'QuickBooks Data')")
    conn_group.add_argument("--filedsn", help="Path to a QODBC .DSN file")
    conn_group.add_argument("--company", help="Path to .QBW company file (direct driver connect)")

    parser.add_argument("--out", help="Output base directory (default: l:/limo/docs/qbw_extracts)")
    parser.add_argument("--since", help="Lower date bound (YYYY-MM-DD)")
    parser.add_argument("--until", help="Upper date bound (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, help="Row limit per view (optional)")

    parser.add_argument(
        "--entities",
        nargs="*",
        default=DEFAULT_ENTITIES,
        help=f"Entity views to export (default: {', '.join(DEFAULT_ENTITIES)})",
    )
    parser.add_argument(
        "--txnviews",
        nargs="*",
        default=DEFAULT_TXN_VIEWS,
        help=f"Transaction views to export (default: {', '.join(DEFAULT_TXN_VIEWS)})",
    )

    args = parser.parse_args()

    # Validate dates
    for label, val in (("since", args.since), ("until", args.until)):
        if val:
            try:
                dt.date.fromisoformat(val)
            except ValueError:
                print(f"[FAIL] Invalid {label} date: {val} (expected YYYY-MM-DD)")
                sys.exit(2)

    conn_str = build_connection_string(args.dsn, args.filedsn, args.company)
    print(f"Connecting via: {conn_str}")

    try:
        conn = pyodbc.connect(conn_str, timeout=30)
    except pyodbc.Error as e:
        print("[FAIL] Failed to connect to QuickBooks via QODBC.")
        print("   Tips: Ensure QuickBooks Desktop is open with the target company, and QODBC is installed & authorized.")
        print(f"   Detail: {e}")
        sys.exit(1)

    out_dir = ensure_output_dir(args.out)
    print(f"Output folder: {out_dir}")

    # Extract core entities
    print("\nExtracting core entities ...")
    entity_results = extract_views(conn, args.entities, out_dir, None, None, args.limit)

    # Extract transactions
    print("\nExtracting transaction views ...")
    txn_results = extract_views(conn, args.txnviews, out_dir, args.since, args.until, args.limit)

    conn.close()

    print("\n[OK] Extraction complete")
    if entity_results:
        total_entities = sum(entity_results.values())
        print(f"  Entities total rows: {total_entities}")
    if txn_results:
        total_txn = sum(txn_results.values())
        print(f"  Transaction views total rows: {total_txn}")
    print(f"  Files written under: {out_dir}")


if __name__ == "__main__":
    main()
