"""
Advanced T4 loader: fill zero-value rows by matching reconciliation entries
to existing DB rows via normalized employee name or SIN.
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Dict

import psycopg2
from psycopg2.extras import execute_batch

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

RECON_PATH = Path(r"L:\\limo\\reports\\T4_RECONCILIATION_REPORT.json")


def norm(s: str | None) -> str | None:
    if not s:
        return None
    return " ".join(s.lower().strip().split())


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def main():
    parser = argparse.ArgumentParser(description="Fill zero-value T4 rows from reconciliation")
    parser.add_argument("--years", default="2013,2014", help="Years to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--write", action="store_true", help="Apply updates")
    args = parser.parse_args()

    if not (args.dry_run or args.write):
        print("Error: Specify --dry-run or --write")
        return

    target_years = [int(y.strip()) for y in args.years.split(",")]
    recon = json.load(open(RECON_PATH))
    conn = connect_db()
    cur = conn.cursor()

    try:
        # Get all DB records for target years
        cur.execute(
            """
            SELECT etr.employee_id, etr.tax_year, e.full_name, e.t4_sin,
                   etr.box_14_employment_income, etr.box_22_income_tax, etr.box_16_cpp_contributions
            FROM employee_t4_records etr
            JOIN employees e ON etr.employee_id = e.employee_id
            WHERE etr.tax_year IN ({})
            """.format(",".join(map(str, target_years)))
        )
        db_records = cur.fetchall()
        
        # Build index: (emp_id, year) → box values
        db_zero_rows = {}  # Maps (emp_id, year) → (box_14, box_22, box_16) if all zero
        for emp_id, year, full_name, t4_sin, box_14, box_22, box_16 in db_records:
            key = (emp_id, year)
            if all(v == 0 for v in [box_14, box_22, box_16]):
                db_zero_rows[key] = (full_name, t4_sin)

        # Build SIN → emp_id map for non-zero rows (to check if already has data)
        sin_to_emp = {}
        for emp_id, year, full_name, t4_sin, box_14, box_22, box_16 in db_records:
            if t4_sin and (box_14 or box_22 or box_16):
                sin_to_emp[t4_sin] = emp_id

        # Build name → emp_id map for zero-value rows
        name_map: Dict[str, int] = {}
        for emp_id, year in db_zero_rows.keys():
            full_name, _ = db_zero_rows[(emp_id, year)]
            nm = norm(full_name)
            if nm:
                name_map[nm] = emp_id

        # Process reconciliation to find candidates to fill zero rows
        update_rows = []
        filled_count = 0

        for year_str, year_data in recon.get("results_by_year", {}).items():
            year = int(year_str)
            if year not in target_years:
                continue

            for entry in year_data.get("pdf_only", []) + year_data.get("discrepancies", []):
                sin = entry.get("sin")
                emp_name = entry.get("employee_name")
                
                # Skip UNKNOWN_PAGE entries (can't map)
                if sin and sin.startswith("UNKNOWN_PAGE"):
                    continue

                boxes = entry.get("boxes", {})
                if not boxes:
                    # Try to extract from discrepancies issues
                    issues = entry.get("issues", [])
                    boxes = {i.get("box"): i.get("pdf_value", 0) for i in issues if i.get("box")}

                if not boxes:
                    continue

                box_14 = float(boxes.get("box_14", 0) or 0)
                box_22 = float(boxes.get("box_22", 0) or 0)
                box_16 = float(boxes.get("box_16", 0) or 0)

                candidate_emp_id = None

                # Try SIN match first
                if sin and sin in sin_to_emp:
                    candidate_emp_id = sin_to_emp[sin]
                elif emp_name:
                    nm = norm(emp_name)
                    if nm in name_map:
                        candidate_emp_id = name_map[nm]

                if candidate_emp_id and (candidate_emp_id, year) in db_zero_rows:
                    update_rows.append((
                        Decimal(str(box_14)),
                        Decimal(str(box_16)),
                        Decimal(str(box_22)),
                        f"Filled zero-value row from reconciliation {year}",
                        candidate_emp_id,
                        year,
                    ))
                    filled_count += 1

        if args.dry_run:
            print(f"📊 Dry-run: Would fill {filled_count} zero-value rows")
        elif args.write and update_rows:
            query = """
                UPDATE employee_t4_records
                SET box_14_employment_income = %s,
                    box_16_cpp_contributions = %s,
                    box_22_income_tax = %s,
                    notes = %s,
                    updated_at = now()
                WHERE employee_id = %s AND tax_year = %s
            """
            execute_batch(cur, query, update_rows, page_size=50)
            conn.commit()
            print(f"✅ Updated {cur.rowcount} zero-value rows")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
