#!/usr/bin/env python3
"""Fix charters.driver to ensure numbers come from employees table.

Strategy:
1) If charters.assigned_driver_id is set, replace driver with employees.employee_number for that id.
2) Else, if charters.driver_name matches employees.full_name (case-insensitive), set driver to that employee's employee_number.
3) Report unmapped cases.

Usage:
  python -X utf8 scripts/fix_charter_driver_numbers.py --dry-run
  python -X utf8 scripts/fix_charter_driver_numbers.py --write --backup

Outputs:
- reports/fix_charter_driver_numbers_summary_<DATE>.csv
- reports/fix_charter_driver_numbers_unmapped_<DATE>.csv
"""
import argparse
import difflib
import csv
import datetime
import os
import psycopg2
import psycopg2.extras as extras

PG = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***"),
    port=int(os.environ.get("DB_PORT", "5432")),
)

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
REPORT_DIR = os.path.join(ROOT_DIR, "reports")
DATE_SUFFIX = datetime.date.today().isoformat()


def write_csv(path: str, headers, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def backup_changes(to_fix):
    # Write CSV of planned changes and SQL rollback script
    changes_csv = os.path.join(REPORT_DIR, f"fix_charter_driver_numbers_changes_{DATE_SUFFIX}.csv")
    write_csv(
        changes_csv,
        ["charter_id", "current_driver", "new_driver", "assigned_driver_id", "secondary_driver_id", "driver_name"],
        to_fix,
    )
    # SQL rollback file
    rollback_sql_path = os.path.join(REPORT_DIR, f"fix_charter_driver_numbers_backup_{DATE_SUFFIX}.sql")
    def esc(s):
        if s is None:
            return "NULL"
        return "'" + str(s).replace("'", "''") + "'"
    with open(rollback_sql_path, "w", encoding="utf-8") as f:
        f.write("BEGIN;\n")
        for cid, current, new_num, assigned_id, sec_id, dname in to_fix:
            # Revert to original current value (may be NULL)
            if current:
                f.write(f"UPDATE charters SET driver={esc(current)} WHERE charter_id={int(cid)};\n")
            else:
                f.write(f"UPDATE charters SET driver=NULL WHERE charter_id={int(cid)};\n")
        f.write("COMMIT;\n")
    print(f"Backup written: {changes_csv} and {rollback_sql_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--fuzzy", action="store_true", help="Enable fuzzy name matching for driver_name → employee_number")
    parser.add_argument("--override-code", action="append", help="Override mapping: CODE:Full Name (e.g., Dr51:Korsh, Jonathan). Can be repeated.")
    args = parser.parse_args()

    os.makedirs(REPORT_DIR, exist_ok=True)

    with psycopg2.connect(**PG) as conn:
        with conn.cursor(cursor_factory=extras.DictCursor) as cur:
            # Build employees lookup
            cur.execute("SELECT employee_id, LOWER(TRIM(COALESCE(full_name,''))) AS name, employee_number FROM employees")
            emp_by_id = {}
            emp_by_name = {}
            emp_names_list = []
            for row in cur.fetchall():
                emp_by_id[row[0]] = row[2]
                if row[1]:
                    emp_by_name[row[1]] = row[2]
                    emp_names_list.append(row[1])

            # Build override mappings CODE -> employee_number via full name provided
            code_overrides = {}
            if args.override_code:
                for item in args.override_code:
                    try:
                        code, name = item.split(":", 1)
                        code = code.strip()
                        norm_name = name.strip().lower()
                        emp_num = emp_by_name.get(norm_name)
                        if emp_num:
                            code_overrides[code] = emp_num
                        else:
                            # Try fuzzy match against names
                            best_match = None
                            best_ratio = 0.0
                            for en in emp_names_list:
                                r = difflib.SequenceMatcher(None, norm_name, en).ratio()
                                if r > best_ratio:
                                    best_ratio = r
                                    best_match = en
                            if best_match and best_ratio >= 0.85:
                                code_overrides[code] = emp_by_name.get(best_match)
                    except ValueError:
                        pass  # ignore malformed entries

            # Identify candidate charters to fix
            # Detect available columns on charters
            cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name='charters'
                """
            )
            ch_cols = {r[0] for r in cur.fetchall()}
            select_fields = ["charter_id", "driver"]
            use_assigned = "assigned_driver_id" in ch_cols
            use_secondary = "secondary_driver_id" in ch_cols
            use_driver_name = "driver_name" in ch_cols
            if use_assigned:
                select_fields.append("assigned_driver_id")
            if use_secondary:
                select_fields.append("secondary_driver_id")
            if use_driver_name:
                select_fields.append("LOWER(TRIM(COALESCE(driver_name,''))) AS driver_name")
            select_sql = f"SELECT {', '.join(select_fields)} FROM charters"
            cur.execute(select_sql)

            to_fix = []
            unmapped = []
            for row in cur.fetchall():
                # Unpack row dynamically
                idx = {name: i for i, name in enumerate([f.split(' AS ')[-1] if ' AS ' in f else f for f in select_fields])}
                cid = row[idx["charter_id"]]
                drv = row[idx["driver"]]
                assigned_id = row[idx["assigned_driver_id"]] if use_assigned else None
                sec_id = row[idx["secondary_driver_id"]] if use_secondary else None
                dname = row[idx["driver_name"]] if use_driver_name else None
                current = (drv or '').strip()
                new_num = None
                # If already a valid employee_number, skip
                if current and current in emp_by_id.values():
                    continue
                # If current is a known override CODE, use its employee_number
                if current in code_overrides:
                    new_num = code_overrides[current]
                # Prefer assigned_driver_id mapping
                if assigned_id and assigned_id in emp_by_id:
                    new_num = emp_by_id[assigned_id]
                # Else try secondary_driver_id
                elif sec_id and sec_id in emp_by_id:
                    new_num = emp_by_id[sec_id]
                # Else try name mapping
                elif dname and dname in emp_by_name:
                    new_num = emp_by_name[dname]
                # Else try fuzzy name match
                elif args.fuzzy and dname and emp_names_list:
                    # Get best close match by normalized name
                    best_match = None
                    best_ratio = 0.0
                    for en in emp_names_list:
                        r = difflib.SequenceMatcher(None, dname, en).ratio()
                        if r > best_ratio:
                            best_ratio = r
                            best_match = en
                    if best_match and best_ratio >= 0.85:
                        new_num = emp_by_name.get(best_match)
                # Prepare action
                if new_num:
                    if not current or current != new_num:
                        to_fix.append([cid, current, new_num, assigned_id, sec_id, dname])
                else:
                    if current:
                        unmapped.append([cid, current, assigned_id, sec_id, dname])

            # Report
            write_csv(
                os.path.join(REPORT_DIR, f"fix_charter_driver_numbers_summary_{DATE_SUFFIX}.csv"),
                ["charters_to_update", "unmapped"],
                [[len(to_fix), len(unmapped)]],
            )
            if unmapped:
                write_csv(
                    os.path.join(REPORT_DIR, f"fix_charter_driver_numbers_unmapped_{DATE_SUFFIX}.csv"),
                    ["charter_id", "current_driver", "assigned_driver_id", "secondary_driver_id", "driver_name"],
                    unmapped,
                )

            # Apply updates
            if args.write:
                if args.backup:
                    backup_changes(to_fix)
                updated = 0
                for cid, current, new_num, assigned_id, sec_id, dname in to_fix:
                    cur.execute(
                        "UPDATE charters SET driver=%s WHERE charter_id=%s",
                        (new_num, cid),
                    )
                    updated += 1
                conn.commit()
                print(f"Applied {updated} updates; committed.")
            else:
                print(f"Dry-run: would update {len(to_fix)} charters; see reports for details.")


if __name__ == "__main__":
    main()
