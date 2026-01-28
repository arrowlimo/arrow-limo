"""
Load T4 PDF details into employee_t4_records DB table.
- Reads T4_PDF_DETAIL_EXPORT.json (from export_t4_pdf_details.py)
- Matches SINs to employee_id via employees.t4_sin
- Inserts deduped (year, employee_id) rows with box values
- Supports --dry-run and --write modes
- Includes conflict handling (skip existing or insert on missing)
"""
from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

EXPORT_PATH = Path(r"L:\\limo\\reports\\T4_PDF_DETAIL_EXPORT.json")


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def load_export() -> list:
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(f"Export not found: {EXPORT_PATH}")
    with open(EXPORT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("dedup_by_year_sin", [])


def main():
    parser = argparse.ArgumentParser(description="Load T4 PDF details into DB")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--write", action="store_true", help="Apply changes")
    args = parser.parse_args()

    if not (args.dry_run or args.write):
        print("Error: Specify --dry-run or --write")
        return

    rows = load_export()
    conn = connect_db()
    cur = conn.cursor()

    try:
        # Build SIN → employee_id map
        cur.execute("SELECT employee_id, t4_sin FROM employees WHERE t4_sin IS NOT NULL")
        sin_map = {row[1]: row[0] for row in cur.fetchall()}

        insert_count = 0
        skip_count = 0
        inserted_rows = []

        for row in rows:
            sin = row["sin"]
            year = row["year"]
            if sin not in sin_map:
                print(f"  ⚠ Skip {year} SIN {sin}: not in employees")
                skip_count += 1
                continue

            employee_id = sin_map[sin]
            box_14 = row.get("box_14", 0)
            box_16 = row.get("box_16", 0)
            box_18 = row.get("box_18", 0)
            box_22 = row.get("box_22", 0)
            box_24 = row.get("box_24", 0)
            box_26 = row.get("box_26", 0)

            # Check if (employee_id, year) already exists
            cur.execute(
                "SELECT 1 FROM employee_t4_records WHERE employee_id = %s AND tax_year = %s",
                (employee_id, year)
            )
            exists = cur.fetchone() is not None

            if exists:
                print(f"  ⏭ Skip {year} EMP {employee_id}: already in DB")
                skip_count += 1
                continue

            inserted_rows.append((
                employee_id,
                year,
                box_14,
                box_16,
                box_18,
                box_22,
                box_24,
                box_26,
                f"Auto-loaded from PDF extraction {year}",
            ))
            insert_count += 1

        print(f"\n📊 Dry-run summary:")
        print(f"  Insert: {insert_count}")
        print(f"  Skip (existing/not-found): {skip_count}")

        if args.dry_run:
            print("\n✅ Dry-run complete. Use --write to apply.")
        elif args.write and inserted_rows:
            query = """
                INSERT INTO employee_t4_records
                (employee_id, tax_year, box_14_employment_income, box_16_cpp_contributions,
                 box_18_ei_premiums, box_22_income_tax, box_24_ei_insurable_earnings,
                 box_26_cpp_pensionable_earnings, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            execute_batch(cur, query, inserted_rows, page_size=100)
            conn.commit()
            print(f"\n✅ Inserted {cur.rowcount} rows")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
