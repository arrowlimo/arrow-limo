"""Ingest August 2012 payroll backfill from a JSON specification.

Dry-run by default. Only writes when --apply provided.

JSON Schema (example):
{
  "period": "2012-08",
  "source": "august_2012_pdf_summary",
  "totals_expected": {
    "gross": 14773.59,
    "cpp": 590.37,
    "ei": 198.50,
    "tax": 2130.50
  },
  "employees": [
    {"employee_id": 62, "full_name": "Douglas Example", "gross": 1857.81, "cpp": 52.10, "ei": 20.70, "tax": 335.10},
    {"employee_id": 3,  "full_name": "Jeannie Shillington", "gross": 1264.31, "cpp": 41.92, "ei": 14.08, "tax": 264.88}
    // ... additional employees
  ]
}

The script will:
1. Validate schema and aggregate totals vs expected.
2. Fetch existing August 2012 WAGE / BACKFILL entries from driver_payroll.
3. Compute per-employee deltas (expected - existing) for gross, cpp, ei, tax.
4. Produce summary table and integrity checks.
5. (Dry-run) Show planned inserts; (Apply) insert only positive deltas above tolerance.

Idempotency: Generates a source_hash per inserted row (SHA256 of employee_id + period + component totals + source string). Skips inserts whose hash already exists.

Rationale: Avoid proportional guesswork; rely on authoritative per-employee PDF totals.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import hashlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date

import psycopg2
import psycopg2.extras


# --- Configuration / Helpers -------------------------------------------------

EXPECTED_PERIOD = "2012-08"  # Hard-coded for safety; refuse other periods unless override flag provided.

@dataclass
class EmployeeExpected:
    employee_id: int
    full_name: str
    gross: float
    cpp: float
    ei: float
    tax: float

@dataclass
class EmployeeExisting:
    employee_id: int
    gross: float = 0.0
    cpp: float = 0.0
    ei: float = 0.0
    tax: float = 0.0

@dataclass
class EmployeeDelta:
    employee_id: int
    full_name: str
    gross_delta: float
    cpp_delta: float
    ei_delta: float
    tax_delta: float
    net_delta: float
    source_hash: str
    skipped_reason: Optional[str] = None


def get_db_connection():
    """Create a PostgreSQL connection using standard environment variables."""
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "almsdata")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "***REMOVED***")
    return psycopg2.connect(host=host, dbname=name, user=user, password=password)


def parse_args():
    p = argparse.ArgumentParser(description="Ingest August 2012 payroll backfill from JSON specification (dry-run by default).")
    p.add_argument("--json", required=True, help="Path to JSON specification file.")
    p.add_argument("--apply", action="store_true", help="Apply inserts (otherwise dry-run).")
    p.add_argument("--allow-period", action="store_true", help="Allow periods other than hard-coded 2012-08.")
    p.add_argument("--tolerance", type=float, default=0.01, help="Rounding tolerance for totals & component deltas.")
    p.add_argument("--verbose", action="store_true", help="Verbose output.")
    return p.parse_args()


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(payload: Dict[str, Any]):
    required_top = {"period", "source", "totals_expected", "employees"}
    missing = required_top - set(payload.keys())
    if missing:
        raise ValueError(f"Missing top-level keys: {sorted(missing)}")
    te = payload["totals_expected"]
    for k in ["gross", "cpp", "ei", "tax"]:
        if k not in te:
            raise ValueError(f"totals_expected is missing '{k}'")
    if not isinstance(payload["employees"], list) or not payload["employees"]:
        raise ValueError("'employees' must be a non-empty list")
    for idx, e in enumerate(payload["employees"]):
        for k in ["employee_id", "full_name", "gross", "cpp", "ei", "tax"]:
            if k not in e:
                raise ValueError(f"Employee entry {idx} missing '{k}'")


def build_expected(payload: Dict[str, Any]) -> Tuple[List[EmployeeExpected], Dict[str, float]]:
    employees = [
        EmployeeExpected(
            employee_id=int(e["employee_id"]),
            full_name=str(e["full_name"]),
            gross=float(e["gross"]),
            cpp=float(e["cpp"]),
            ei=float(e["ei"]),
            tax=float(e["tax"]),
        )
        for e in payload["employees"]
    ]
    totals = {
        "gross": float(payload["totals_expected"]["gross"]),
        "cpp": float(payload["totals_expected"]["cpp"]),
        "ei": float(payload["totals_expected"]["ei"]),
        "tax": float(payload["totals_expected"]["tax"]),
    }
    return employees, totals


def fetch_existing(conn, year: int, month: int) -> Dict[int, EmployeeExisting]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    # Filter only wage/backfill classes; exclude adjustments.
    cur.execute(
        """
        SELECT employee_id, COALESCE(gross_pay,0) AS gross_pay,
               COALESCE(cpp,0) AS cpp, COALESCE(ei,0) AS ei,
               COALESCE(tax,0) AS tax
        FROM driver_payroll
        WHERE year = %s AND month = %s
          AND (payroll_class IS NULL OR payroll_class IN ('WAGE','BACKFILL'))
    """,
        (year, month),
    )
    rows = cur.fetchall()
    existing: Dict[int, EmployeeExisting] = {}
    for r in rows:
        eid = r["employee_id"]
        if eid is None:
            continue
        ex = existing.get(eid, EmployeeExisting(employee_id=eid))
        ex.gross += float(r["gross_pay"])
        ex.cpp += float(r["cpp"])
        ex.ei += float(r["ei"])
        ex.tax += float(r["tax"])
        existing[eid] = ex
    cur.close()
    return existing


def hash_row(e: EmployeeExpected, period: str, source: str) -> str:
    h = hashlib.sha256()
    h.update(f"{period}|{source}|{e.employee_id}|{e.gross:.2f}|{e.cpp:.2f}|{e.ei:.2f}|{e.tax:.2f}".encode("utf-8"))
    return h.hexdigest()[:32]


def existing_hashes(conn, period: str) -> set:
    year, month = map(int, period.split("-"))
    cur = conn.cursor()
    cur.execute(
        """
        SELECT source_hash FROM driver_payroll
        WHERE year=%s AND month=%s AND payroll_class='BACKFILL' AND source_hash IS NOT NULL
        """,
        (year, month),
    )
    hs = {r[0] for r in cur.fetchall() if r[0]}
    cur.close()
    return hs


def compute_deltas(expected: List[EmployeeExpected], existing: Dict[int, EmployeeExisting], period: str, source: str, tolerance: float) -> List[EmployeeDelta]:
    deltas: List[EmployeeDelta] = []
    for e in expected:
        ex = existing.get(e.employee_id, EmployeeExisting(employee_id=e.employee_id))
        gross_delta = round(e.gross - ex.gross, 2)
        cpp_delta = round(e.cpp - ex.cpp, 2)
        ei_delta = round(e.ei - ex.ei, 2)
        tax_delta = round(e.tax - ex.tax, 2)
        net_delta = round(gross_delta - (cpp_delta + ei_delta + tax_delta), 2)
        source_hash = hash_row(e, period, source)
        reason: Optional[str] = None
        if gross_delta < tolerance and cpp_delta < tolerance and ei_delta < tolerance and tax_delta < tolerance:
            reason = "ALREADY_PRESENT_OR_WITHIN_TOLERANCE"
        elif gross_delta < -tolerance or cpp_delta < -tolerance or ei_delta < -tolerance or tax_delta < -tolerance:
            reason = "NEGATIVE_DELTA_CHECK_MANUALLY"
        deltas.append(
            EmployeeDelta(
                employee_id=e.employee_id,
                full_name=e.full_name,
                gross_delta=gross_delta,
                cpp_delta=cpp_delta,
                ei_delta=ei_delta,
                tax_delta=tax_delta,
                net_delta=net_delta,
                source_hash=source_hash,
                skipped_reason=reason,
            )
        )
    return deltas


def print_summary(expected_totals: Dict[str, float], existing: Dict[int, EmployeeExisting], deltas: List[EmployeeDelta]):
    total_existing = {"gross":0.0,"cpp":0.0,"ei":0.0,"tax":0.0}
    for ex in existing.values():
        total_existing["gross"] += ex.gross
        total_existing["cpp"] += ex.cpp
        total_existing["ei"] += ex.ei
        total_existing["tax"] += ex.tax
    total_missing = {"gross":0.0,"cpp":0.0,"ei":0.0,"tax":0.0}
    for d in deltas:
        if not d.skipped_reason:
            total_missing["gross"] += max(d.gross_delta,0)
            total_missing["cpp"] += max(d.cpp_delta,0)
            total_missing["ei"] += max(d.ei_delta,0)
            total_missing["tax"] += max(d.tax_delta,0)
    print("\n=== AGGREGATE SUMMARY ===")
    print(f"Expected Gross: {expected_totals['gross']:.2f}")
    print(f"Existing Gross: {total_existing['gross']:.2f}")
    print(f"Missing Gross:  {total_missing['gross']:.2f}")
    print(f"Expected CPP:   {expected_totals['cpp']:.2f} | Missing: {total_missing['cpp']:.2f}")
    print(f"Expected EI:    {expected_totals['ei']:.2f} | Missing: {total_missing['ei']:.2f}")
    print(f"Expected Tax:   {expected_totals['tax']:.2f} | Missing: {total_missing['tax']:.2f}")
    print("==========================\n")

    print("EMPLOYEE DELTAS (gross, cpp, ei, tax, net)")
    header = f"{'EmpID':>6} {'GrossΔ':>10} {'CPPΔ':>8} {'EIΔ':>8} {'TaxΔ':>9} {'NetΔ':>10} {'Status':>26}"
    print(header)
    print('-'*len(header))
    for d in sorted(deltas, key=lambda x: (-max(x.gross_delta,0), x.employee_id)):
        status = d.skipped_reason or 'INSERT'
        print(f"{d.employee_id:>6} {d.gross_delta:>10.2f} {d.cpp_delta:>8.2f} {d.ei_delta:>8.2f} {d.tax_delta:>9.2f} {d.net_delta:>10.2f} {status:>26}")


def perform_inserts(conn, deltas: List[EmployeeDelta], period: str, source: str, tolerance: float, existing_backfill_hashes: set):
    year, month = map(int, period.split('-'))
    cur = conn.cursor()
    inserted = 0
    for d in deltas:
        if d.skipped_reason:
            continue
        if d.source_hash in existing_backfill_hashes:
            print(f"SKIP hash exists: {d.employee_id} {d.source_hash}")
            continue
        if d.gross_delta <= tolerance and d.cpp_delta <= tolerance and d.ei_delta <= tolerance and d.tax_delta <= tolerance:
            continue
        net_pay = round(d.gross_delta - (d.cpp_delta + d.ei_delta + d.tax_delta), 2)
        # Prepare safe INSERT with only existing columns.
        # Introspect columns first.
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name='driver_payroll'
            """
        )
        cols_available = {r[0] for r in cur.fetchall()}
        insert_cols = ["employee_id", "year", "month", "gross_pay", "cpp", "ei", "tax", "net_pay", "payroll_class", "source", "imported_at", "source_hash"]
        data_map = {
            "employee_id": d.employee_id,
            "year": year,
            "month": month,
            "gross_pay": d.gross_delta,
            "cpp": d.cpp_delta,
            "ei": d.ei_delta,
            "tax": d.tax_delta,
            "net_pay": net_pay,
            "payroll_class": "BACKFILL",
            "source": source,
            "imported_at": datetime.utcnow(),
            "source_hash": d.source_hash,
        }
        # Filter to only columns that actually exist.
        final_cols = [c for c in insert_cols if c in cols_available]
        placeholders = ",".join(["%s"] * len(final_cols))
        col_list = ",".join(final_cols)
        values = [data_map[c] for c in final_cols]
        sql = f"INSERT INTO driver_payroll ({col_list}) VALUES ({placeholders})"
        cur.execute(sql, values)
        inserted += 1
    conn.commit()
    cur.close()
    print(f"Inserted {inserted} backfill rows.")


def main():
    args = parse_args()
    payload = load_json(args.json)
    validate_schema(payload)
    period = payload["period"]
    source = payload["source"]
    if period != EXPECTED_PERIOD and not args.allow_period:
        print(f"ERROR: Period {period} not allowed (expected {EXPECTED_PERIOD}). Use --allow-period to override.", file=sys.stderr)
        sys.exit(2)
    expected_employees, expected_totals = build_expected(payload)

    # Validate aggregate expected totals matches employee sum.
    sum_check = {"gross":0.0,"cpp":0.0,"ei":0.0,"tax":0.0}
    for e in expected_employees:
        sum_check["gross"] += e.gross
        sum_check["cpp"] += e.cpp
        sum_check["ei"] += e.ei
        sum_check["tax"] += e.tax
    for k in sum_check:
        if abs(sum_check[k] - expected_totals[k]) > args.tolerance:
            print(f"ERROR: Expected totals mismatch for {k}: header={expected_totals[k]:.2f} sum(employees)={sum_check[k]:.2f}", file=sys.stderr)
            sys.exit(3)

    year, month = map(int, period.split('-'))
    conn = get_db_connection()
    existing_map = fetch_existing(conn, year, month)
    backfill_hashes = existing_hashes(conn, period)
    deltas = compute_deltas(expected_employees, existing_map, period, source, args.tolerance)
    print_summary(expected_totals, existing_map, deltas)

    planned_inserts = [d for d in deltas if not d.skipped_reason and d.gross_delta > args.tolerance]
    print(f"Planned INSERT rows: {len(planned_inserts)} (apply={args.apply})")
    if not args.apply:
        print("Dry-run complete. No changes applied.")
        conn.close()
        return

    perform_inserts(conn, deltas, period, source, args.tolerance, backfill_hashes)
    conn.close()


if __name__ == "__main__":
    main()
