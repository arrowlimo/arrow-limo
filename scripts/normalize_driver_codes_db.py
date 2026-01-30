"""Normalize driver_code capitalization (DR prefix) and zero-pad numeric parts.

Defaults to DRY RUN. Use --write to commit.
"""

import os
import psycopg2

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")


def normalize_code(raw: str) -> str:
    if raw is None:
        return None
    value = raw.strip().upper().replace(" ", "")

    # Numeric only -> DR## (1-2 digits) or DR### (100+)
    if value.isdigit():
        num = int(value)
        return f"DR{num:02d}" if num < 100 else f"DR{num}"

    # D## -> DR## (1-2 digits) or DR### (100+)
    if value.startswith("D") and value[1:].isdigit():
        num = int(value[1:])
        return f"DR{num:02d}" if num < 100 else f"DR{num}"

    # DR## -> DR## (1-2 digits) or DR### (100+)
    if value.startswith("DR") and value[2:].isdigit():
        num = int(value[2:])
        return f"DR{num:02d}" if num < 100 else f"DR{num}"

    # H## -> H## (2-digit)
    if value.startswith("H") and value[1:].isdigit():
        return f"H{int(value[1:]):02d}"

    # OF## -> OF## (2-digit)
    if value.startswith("OF") and value[2:].isdigit():
        return f"OF{int(value[2:]):02d}"

    return value


def process_table(cur, table: str, column: str, id_column: str):
    cur.execute(f"SELECT {id_column}, {column} FROM {table} WHERE {column} IS NOT NULL")
    rows = cur.fetchall()

    updates = []
    for row_id, code in rows:
        normalized = normalize_code(code)
        if normalized != code:
            updates.append((normalized, row_id, code))

    return updates


def apply_updates(cur, table: str, column: str, id_column: str, updates, dry_run: bool):
    if not updates:
        print(f"✅ {table}.{column}: no changes needed")
        return 0

    print(f"{table}.{column}: {len(updates)} updates")
    for normalized, row_id, old in updates[:10]:
        print(f"  {old} -> {normalized}")

    if not dry_run:
        cur.executemany(
            f"UPDATE {table} SET {column} = %s WHERE {id_column} = %s",
            [(n, i) for n, i, _ in updates],
        )

    return len(updates)


def fetch_distinct_codes(cur, table: str, column: str):
    cur.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
    return [row[0] for row in cur.fetchall()]


def sort_codes(codes):
    def key_func(code):
        if code is None:
            return ("ZZ", 999999, "")
        value = code.strip().upper().replace(" ", "")

        prefix = ""
        num_part = ""
        for ch in value:
            if ch.isdigit():
                num_part += ch
            else:
                prefix += ch

        num = int(num_part) if num_part.isdigit() else 999999
        return (prefix, num, value)

    return sorted(codes, key=key_func)


def print_grouped_codes(title: str, codes):
    print("\n" + title)
    print("-" * len(title))
    grouped = {}
    for code in codes:
        if code is None:
            continue
        value = code.strip().upper().replace(" ", "")
        prefix = ""
        for ch in value:
            if not ch.isdigit():
                prefix += ch
            else:
                break
        grouped.setdefault(prefix, []).append(value)

    for prefix in sorted(grouped.keys()):
        sorted_codes = sort_codes(grouped[prefix])
        print(f"{prefix}: {', '.join(sorted_codes[:50])}")
        if len(sorted_codes) > 50:
            print(f"  ... ({len(sorted_codes)} total)")


def main(dry_run: bool):
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cur = conn.cursor()

    print("=" * 80)
    print("DRIVER CODE NORMALIZATION")
    print("=" * 80)
    print(f"Mode: {'DRY RUN' if dry_run else 'WRITE'}")

    total_updates = 0

    # LMS staging
    updates = process_table(cur, "lms2026_reserves", "driver_code", "id")
    total_updates += apply_updates(cur, "lms2026_reserves", "driver_code", "id", updates, dry_run)

    # Employees master
    updates = process_table(cur, "employees", "driver_code", "employee_id")
    total_updates += apply_updates(cur, "employees", "driver_code", "employee_id", updates, dry_run)

    if not dry_run:
        conn.commit()
        print("✅ Updates committed")
    else:
        print("ℹ️  Dry run only. Use --write to commit.")

    print(f"Total updates: {total_updates}")

    lms_codes = fetch_distinct_codes(cur, "lms2026_reserves", "driver_code")
    employees_codes = fetch_distinct_codes(cur, "employees", "driver_code")

    print_grouped_codes("LMS driver codes (grouped, numeric sort)", lms_codes)
    print_grouped_codes("Employees driver codes (grouped, numeric sort)", employees_codes)

    cur.close()
    conn.close()


if __name__ == "__main__":
    import sys

    dry_run = "--write" not in sys.argv
    main(dry_run)
