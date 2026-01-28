"""
Load T4 data from reconciliation report into DB.
- Reads T4_RECONCILIATION_REPORT.json (which has SINs and PDF box values)
- Matches SINs to employees
- Inserts missing (year, employee_id) records with PDF values
- Focus on 2013/2014 which are completely missing from DB
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import csv
from typing import Dict

import psycopg2
from psycopg2.extras import execute_batch

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

RECON_PATH = Path(r"L:\\limo\\reports\\T4_RECONCILIATION_REPORT.json")


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def load_reconciliation() -> dict:
    if not RECON_PATH.exists():
        raise FileNotFoundError(f"Reconciliation report not found: {RECON_PATH}")
    with open(RECON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Load T4 reconciliation data into DB")
    parser.add_argument("--years", default="2013,2014", help="Years to load (default: 2013,2014)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--write", action="store_true", help="Apply inserts")
    parser.add_argument("--update", action="store_true", help="Update existing rows that have zero box values")
    parser.add_argument("--name-match", action="store_true", help="Enable strict name-based matching when SIN not found")
    parser.add_argument("--mapping-file", type=str, default="", help="Optional CSV mapping file with columns: employee_name,t4_sin,employee_id")
    args = parser.parse_args()

    if not (args.dry_run or args.write):
        print("Error: Specify --dry-run or --write")
        return

    target_years = [int(y.strip()) for y in args.years.split(",")]
    recon = load_reconciliation()
    conn = connect_db()
    cur = conn.cursor()

    try:
        # Build SIN → employee_id map
        cur.execute("SELECT employee_id, t4_sin FROM employees WHERE t4_sin IS NOT NULL")
        sin_map = {row[1]: row[0] for row in cur.fetchall()}

        # Build normalized name → employee_id map (strict exact normalization)
        def norm(s: str | None) -> str | None:
            if not s:
                return None
            # Lowercase, strip, collapse inner whitespace
            return " ".join(s.lower().strip().split())

        name_map: Dict[str, int] = {}
        if args.name_match:
            cur.execute(
                """
                SELECT employee_id, full_name, name, legacy_name, first_name, last_name
                FROM employees
                """
            )
            for emp_id, full_name, name, legacy_name, first_name, last_name in cur.fetchall():
                candidates = set()
                for raw in (full_name, name, legacy_name):
                    n = norm(raw)
                    if n:
                        candidates.add(n)
                # Combine first + last
                fl = norm("{} {}".format(first_name or "", last_name or ""))
                lf = norm("{} {}".format(last_name or "", first_name or ""))
                if fl:
                    candidates.add(fl)
                if lf:
                    candidates.add(lf)
                for cand in candidates:
                    # Only add if unique; if duplicate name appears, mark as ambiguous later
                    if cand not in name_map:
                        name_map[cand] = emp_id
                    else:
                        # Mark ambiguous by setting to -1 (special value)
                        name_map[cand] = -1

        # Optional external mapping file support
        external_name_to_emp: Dict[str, int] = {}
        external_name_to_sin: Dict[str, str] = {}
        if args.mapping_file:
            mf_path = Path(args.mapping_file)
            if mf_path.exists():
                with open(mf_path, "r", encoding="utf-8") as mf:
                    reader = csv.DictReader(mf)
                    for row in reader:
                        nm = norm(row.get("employee_name"))
                        emp_id_str = row.get("employee_id")
                        sin_val = row.get("t4_sin")
                        if nm:
                            if emp_id_str and emp_id_str.strip():
                                try:
                                    external_name_to_emp[nm] = int(emp_id_str)
                                except ValueError:
                                    pass
                            if sin_val and sin_val.strip():
                                external_name_to_sin[nm] = sin_val.strip()

        insert_count = 0
        update_count = 0
        skip_count = 0
        insert_rows = []
        update_rows = []
        seen_keys = set()  # Track (employee_id, year) to deduplicate
        missing_rows = []  # Collect unmapped/skipped entries for reporting

        results_by_year = recon.get("results_by_year", {})
        for year_str, year_data in results_by_year.items():
            year = int(year_str)
            if year not in target_years:
                continue

            print(f"\n📋 Processing {year}:")

            # Process PDF-only entries (not in DB)
            pdf_only = year_data.get("pdf_only", [])
            for entry in pdf_only:
                sin = entry.get("sin")
                employee_id = None
                match_source = None
                if sin in sin_map:
                    employee_id = sin_map[sin]
                    match_source = "sin"
                else:
                    # Attempt strict name match if enabled
                    emp_name = entry.get("employee_name")
                    nm = norm(emp_name)
                    if nm and args.mapping_file:
                        # External mapping has highest priority when provided
                        if nm in external_name_to_emp:
                            employee_id = external_name_to_emp[nm]
                            match_source = "mapping:employee_id"
                        elif nm in external_name_to_sin and external_name_to_sin[nm] in sin_map:
                            employee_id = sin_map[external_name_to_sin[nm]]
                            match_source = "mapping:t4_sin"
                        elif args.name_match:
                            # Fall back to internal strict name map
                            if nm in name_map and name_map[nm] > 0:
                                employee_id = name_map[nm]
                                match_source = "name"
                            elif nm in name_map and name_map[nm] == -1:
                                print(f"  ⚠ Ambiguous name match '{emp_name}' → multiple employees")
                                skip_count += 1
                                missing_rows.append({
                                    "year": year,
                                    "source": "pdf_only",
                                    "sin": sin,
                                    "employee_name": emp_name,
                                    "reason": "ambiguous name match",
                                    "boxes": json.dumps(entry.get("boxes", {})),
                                })
                                continue
                            else:
                                print(f"  ⚠ Name not matched: '{emp_name}'")
                                skip_count += 1
                                missing_rows.append({
                                    "year": year,
                                    "source": "pdf_only",
                                    "sin": sin,
                                    "employee_name": emp_name,
                                    "reason": "name not found",
                                    "boxes": json.dumps(entry.get("boxes", {})),
                                })
                                continue
                    elif args.name_match and nm:
                        if nm in name_map and name_map[nm] > 0:
                            employee_id = name_map[nm]
                            match_source = "name"
                        elif nm in name_map and name_map[nm] == -1:
                            print(f"  ⚠ Ambiguous name match '{emp_name}' → multiple employees")
                            skip_count += 1
                            missing_rows.append({
                                "year": year,
                                "source": "pdf_only",
                                "sin": sin,
                                "employee_name": emp_name,
                                "reason": "ambiguous name match",
                                "boxes": json.dumps(entry.get("boxes", {})),
                            })
                            continue
                        else:
                            print(f"  ⚠ Name not matched: '{emp_name}'")
                            skip_count += 1
                            missing_rows.append({
                                "year": year,
                                "source": "pdf_only",
                                "sin": sin,
                                "employee_name": emp_name,
                                "reason": "name not found",
                                "boxes": json.dumps(entry.get("boxes", {})),
                            })
                            continue
                    else:
                        print(f"  ⚠ Skip SIN {sin}: not in employees")
                        skip_count += 1
                        missing_rows.append({
                            "year": year,
                            "source": "pdf_only",
                            "sin": sin,
                            "employee_name": emp_name,
                            "reason": "SIN not found in employees",
                            "boxes": json.dumps(entry.get("boxes", {})),
                        })
                        continue

                key = (employee_id, year)
                
                # Check if we already queued this (year, employee_id)
                if key in seen_keys:
                    print(f"  ⏭ Skip SIN {sin}: already queued")
                    skip_count += 1
                    missing_rows.append({
                        "year": year,
                        "source": "pdf_only",
                        "sin": sin,
                        "employee_name": entry.get("employee_name"),
                        "reason": "already queued",
                        "boxes": json.dumps(entry.get("boxes", {})),
                    })
                    continue

                # Check if already in DB and optionally update
                cur.execute(
                    "SELECT box_14_employment_income, box_16_cpp_contributions, box_18_ei_premiums, box_22_income_tax, box_24_ei_insurable_earnings, box_26_cpp_pensionable_earnings FROM employee_t4_records WHERE employee_id = %s AND tax_year = %s",
                    (employee_id, year)
                )
                row = cur.fetchone()
                exists = row is not None

                # Extract boxes from PDF values
                boxes = entry.get("boxes", {})
                box_14 = boxes.get("box_14", 0) or 0
                box_16 = boxes.get("box_16", 0) or 0
                box_18 = boxes.get("box_18", 0) or 0
                box_22 = boxes.get("box_22", 0) or 0
                box_24 = boxes.get("box_24", 0) or 0
                box_26 = boxes.get("box_26", 0) or 0

                if exists:
                    if args.update and row and all((val == 0 for val in row)):
                        # Queue update for existing zero-value row
                        update_rows.append((
                            box_14,
                            box_16,
                            box_18,
                            box_22,
                            box_24,
                            box_26,
                            f"Updated from PDF-only reconciliation {year} ({match_source})",
                            employee_id,
                            year,
                        ))
                        seen_keys.add(key)
                        update_count += 1
                        print(f"  ✓ Queue UPDATE {year} SIN {sin} (emp {employee_id})")
                    else:
                        print(f"  ⏭ Skip SIN {sin}: already in DB (no update)")
                        skip_count += 1
                        missing_rows.append({
                            "year": year,
                            "source": "pdf_only",
                            "sin": sin,
                            "employee_name": entry.get("employee_name"),
                            "reason": "already in DB (no update)",
                            "boxes": json.dumps(entry.get("boxes", {})),
                        })
                else:
                    insert_rows.append((
                        employee_id,
                        year,
                        box_14,
                        box_16,
                        box_18,
                        box_22,
                        box_24,
                        box_26,
                        f"Auto-loaded from PDF-only reconciliation {year} ({match_source})",
                    ))
                    seen_keys.add(key)
                    insert_count += 1
                    print(f"  ✓ Queue INSERT {year} SIN {sin} (emp {employee_id})")

            # Also process discrepancies: use pdf_value per box to populate
            discrepancies = year_data.get("discrepancies", [])
            for entry in discrepancies:
                sin = entry.get("sin")
                employee_id = None
                match_source = None
                if sin in sin_map:
                    employee_id = sin_map[sin]
                    match_source = "sin"
                else:
                    emp_name = entry.get("employee_name")
                    nm = norm(emp_name)
                    issues = entry.get("issues", [])
                    boxes = {i.get("box"): i.get("pdf_value", 0) for i in issues if i.get("box")}
                    if nm and args.mapping_file:
                        if nm in external_name_to_emp:
                            employee_id = external_name_to_emp[nm]
                            match_source = "mapping:employee_id"
                        elif nm in external_name_to_sin and external_name_to_sin[nm] in sin_map:
                            employee_id = sin_map[external_name_to_sin[nm]]
                            match_source = "mapping:t4_sin"
                        elif args.name_match:
                            if nm in name_map and name_map[nm] > 0:
                                employee_id = name_map[nm]
                                match_source = "name"
                            elif nm in name_map and name_map[nm] == -1:
                                print(f"  ⚠ Ambiguous name match '{emp_name}' → multiple employees")
                                skip_count += 1
                                missing_rows.append({
                                    "year": year,
                                    "source": "discrepancies",
                                    "sin": sin,
                                    "employee_name": emp_name,
                                    "reason": "ambiguous name match",
                                    "boxes": json.dumps(boxes),
                                })
                                continue
                            else:
                                print(f"  ⚠ Name not matched: '{emp_name}'")
                                skip_count += 1
                                missing_rows.append({
                                    "year": year,
                                    "source": "discrepancies",
                                    "sin": sin,
                                    "employee_name": emp_name,
                                    "reason": "name not found",
                                    "boxes": json.dumps(boxes),
                                })
                                continue
                    elif args.name_match and nm:
                        if nm in name_map and name_map[nm] > 0:
                            employee_id = name_map[nm]
                            match_source = "name"
                        elif nm in name_map and name_map[nm] == -1:
                            print(f"  ⚠ Ambiguous name match '{emp_name}' → multiple employees")
                            skip_count += 1
                            missing_rows.append({
                                "year": year,
                                "source": "discrepancies",
                                "sin": sin,
                                "employee_name": emp_name,
                                "reason": "ambiguous name match",
                                "boxes": json.dumps(boxes),
                            })
                            continue
                        else:
                            print(f"  ⚠ Name not matched: '{emp_name}'")
                            skip_count += 1
                            missing_rows.append({
                                "year": year,
                                "source": "discrepancies",
                                "sin": sin,
                                "employee_name": emp_name,
                                "reason": "name not found",
                                "boxes": json.dumps(boxes),
                            })
                            continue
                    else:
                        print(f"  ⚠ Skip SIN {sin}: not in employees")
                        skip_count += 1
                        missing_rows.append({
                            "year": year,
                            "source": "discrepancies",
                            "sin": sin,
                            "employee_name": emp_name,
                            "reason": "SIN not found in employees",
                            "boxes": json.dumps(boxes),
                        })
                        continue

                employee_id = sin_map[sin]
                key = (employee_id, year)

                # Build boxes from issues
                issues = entry.get("issues", [])
                boxes = {i.get("box"): i.get("pdf_value", 0) for i in issues if i.get("box")}
                box_14 = boxes.get("box_14", 0) or 0
                box_16 = boxes.get("box_16", 0) or 0
                box_18 = boxes.get("box_18", 0) or 0
                box_22 = boxes.get("box_22", 0) or 0
                box_24 = boxes.get("box_24", 0) or 0
                box_26 = boxes.get("box_26", 0) or 0

                # Check DB row
                cur.execute(
                    "SELECT box_14_employment_income, box_16_cpp_contributions, box_18_ei_premiums, box_22_income_tax, box_24_ei_insurable_earnings, box_26_cpp_pensionable_earnings FROM employee_t4_records WHERE employee_id = %s AND tax_year = %s",
                    (employee_id, year)
                )
                row = cur.fetchone()
                exists = row is not None

                if exists:
                    if args.update and row and all((val == 0 for val in row)):
                        update_rows.append((
                            box_14,
                            box_16,
                            box_18,
                            box_22,
                            box_24,
                            box_26,
                            f"Updated from discrepancies {year} ({match_source})",
                            employee_id,
                            year,
                        ))
                        seen_keys.add(key)
                        update_count += 1
                        print(f"  ✓ Queue UPDATE {year} SIN {sin} (emp {employee_id})")
                    else:
                        print(f"  ⏭ Skip SIN {sin}: already in DB (no update)")
                        skip_count += 1
                        missing_rows.append({
                            "year": year,
                            "source": "discrepancies",
                            "sin": sin,
                            "employee_name": entry.get("employee_name"),
                            "reason": "already in DB (no update)",
                            "boxes": json.dumps(boxes),
                        })
                else:
                    insert_rows.append((
                        employee_id,
                        year,
                        box_14,
                        box_16,
                        box_18,
                        box_22,
                        box_24,
                        box_26,
                        f"Auto-loaded from discrepancies {year} ({match_source})",
                    ))
                    seen_keys.add(key)
                    insert_count += 1
                    print(f"  ✓ Queue INSERT {year} SIN {sin} (emp {employee_id})")

        # Write missing-mappings CSV report
        reports_dir = Path(r"L:\\limo\\reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        missing_csv = reports_dir / "T4_MISSING_MAPPINGS.csv"
        with open(missing_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["year", "source", "sin", "employee_name", "reason", "boxes"])
            writer.writeheader()
            for row in missing_rows:
                writer.writerow(row)

        print(f"\n📊 Summary:")
        print(f"  Insert queued: {insert_count}")
        print(f"  Update queued: {update_count}")
        print(f"  Skip: {skip_count}")
        print(f"  Missing-mappings report: {missing_csv}")

        if args.dry_run:
            print("\n✅ Dry-run complete. Use --write to apply.")
        elif args.write and (insert_rows or update_rows):
            if insert_rows:
                query_ins = """
                    INSERT INTO employee_t4_records
                    (employee_id, tax_year, box_14_employment_income, box_16_cpp_contributions,
                     box_18_ei_premiums, box_22_income_tax, box_24_ei_insurable_earnings,
                     box_26_cpp_pensionable_earnings, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                execute_batch(cur, query_ins, insert_rows, page_size=100)
                conn.commit()
                print(f"\n✅ Inserted {cur.rowcount} rows")

            # Updates use a different shape (boxes..., notes, employee_id, year)
            if update_rows:
                query_upd = """
                    UPDATE employee_t4_records
                    SET box_14_employment_income = %s,
                        box_16_cpp_contributions = %s,
                        box_18_ei_premiums = %s,
                        box_22_income_tax = %s,
                        box_24_ei_insurable_earnings = %s,
                        box_26_cpp_pensionable_earnings = %s,
                        notes = %s,
                        updated_at = now()
                    WHERE employee_id = %s AND tax_year = %s
                """
                execute_batch(cur, query_upd, update_rows, page_size=100)
                conn.commit()
                print(f"\n✅ Updated {cur.rowcount} rows")
        elif args.write:
            print("\n⚠ No rows to insert")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
