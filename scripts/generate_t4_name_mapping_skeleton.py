"""
Generate a suggested T4 name→SIN/employee_id mapping CSV to assist
populating `data/T4_NAME_SIN_MAPPING.csv`.

Inputs:
- reports/T4_MISSING_MAPPINGS.csv (produced by load_t4_recon_to_db.py)
- employees table (for names + t4_sin + employee_id)

Outputs:
- data/T4_NAME_SIN_MAPPING_suggested.csv

Logic:
- Normalize names (lowercase, trim, collapse spaces).
- For each missing entry with an employee_name:
  - Attempt exact normalized match against employees name variants.
  - If unique match, write row with employee_name, t4_sin, employee_id.
  - If ambiguous or not found, still write row with employee_name and blanks
    so the user can fill it manually.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Tuple, List

import psycopg2

DB_HOST = "localhost"
DB_NAME = "almsdata"
DB_USER = "postgres"
DB_PASSWORD = os.environ.get("DB_PASSWORD")

REPORT_CSV = Path(r"L:\\limo\\reports\\T4_MISSING_MAPPINGS.csv")
OUT_CSV = Path(r"L:\\limo\\data\\T4_NAME_SIN_MAPPING_suggested.csv")


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


def build_employee_name_index(cur) -> Tuple[Dict[str, int], Dict[int, Dict[str, str]]]:
    """Return (name_index, emp_details).

    name_index maps normalized name → employee_id (or -1 for ambiguous).
    emp_details maps employee_id → {"t4_sin": str, "full_name": str}
    """
    name_index: Dict[str, int] = {}
    emp_details: Dict[int, Dict[str, str]] = {}

    cur.execute(
        """
        SELECT employee_id, full_name, name, legacy_name, first_name, last_name, t4_sin
        FROM employees
        """
    )
    for emp_id, full_name, name, legacy_name, first_name, last_name, t4_sin in cur.fetchall():
        emp_details[emp_id] = {
            "t4_sin": t4_sin or "",
            "full_name": full_name or name or legacy_name or "",
        }
        candidates = set()
        for raw in (full_name, name, legacy_name):
            n = norm(raw)
            if n:
                candidates.add(n)
        fl = norm(f"{first_name or ''} {last_name or ''}")
        lf = norm(f"{last_name or ''} {first_name or ''}")
        if fl:
            candidates.add(fl)
        if lf:
            candidates.add(lf)
        for cand in candidates:
            if cand not in name_index:
                name_index[cand] = emp_id
            else:
                name_index[cand] = -1
    return name_index, emp_details


def read_missing_rows() -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    if not REPORT_CSV.exists():
        return rows
    with open(REPORT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def main():
    missing_rows = read_missing_rows()
    if not missing_rows:
        print(f"⚠ No missing mappings found at: {REPORT_CSV}")
        return

    conn = connect_db()
    cur = conn.cursor()
    try:
        name_index, emp_details = build_employee_name_index(cur)

        # Deduplicate by employee_name across years/sources; prefer rows with a name
        seen_names = set()
        out_rows: List[Dict[str, str]] = []
        for r in missing_rows:
            emp_name = r.get("employee_name") or ""
            nm = norm(emp_name)
            if not nm:
                # No name present; still output a blank for manual fill
                if emp_name not in seen_names:
                    out_rows.append({
                        "employee_name": emp_name,
                        "t4_sin": "",
                        "employee_id": "",
                    })
                    seen_names.add(emp_name)
                continue

            if emp_name in seen_names:
                continue

            if nm in name_index and name_index[nm] > 0:
                emp_id = name_index[nm]
                det = emp_details.get(emp_id, {})
                out_rows.append({
                    "employee_name": emp_name,
                    "t4_sin": det.get("t4_sin", ""),
                    "employee_id": str(emp_id),
                })
            else:
                # ambiguous or not found
                out_rows.append({
                    "employee_name": emp_name,
                    "t4_sin": "",
                    "employee_id": "",
                })
            seen_names.add(emp_name)

        OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["employee_name", "t4_sin", "employee_id"])
            writer.writeheader()
            for row in out_rows:
                writer.writerow(row)

        print(f"✅ Suggested mapping written: {OUT_CSV}")
        print(f"   Rows: {len(out_rows)}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
