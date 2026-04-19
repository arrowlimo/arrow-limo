#!/usr/bin/env python3
"""
Dry-run GL code consolidation plan for receipts.
- No DB updates are executed.
- Produces impact report + apply SQL + rollback SQL.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "almsdata",
    "user": "postgres",
    "password": "ArrowLimousine",
}

# Canonicalization map agreed from audit clusters.
# Keep NSF split (5715 vs 6800) unchanged pending policy choice.
REMAP = [
    ("2220", "2210", "duplicate account name: Vehicle Operating Leases"),
    ("5410", "5710", "bank service charges into canonical bank fees"),
    ("6500", "5720", "square processing into card processing"),
    ("5450", "5720", "generic payment processing into card processing"),
    ("6200", "5116", "inactive hospitality code into active amenities code"),
    ("5325", "6100", "business meals into meals canonical for T2 handling"),
    ("5140", "5180", "vehicle registration duplicate family"),
    ("5610", "5600", "advertising into marketing & advertising"),
    ("6130", "5600", "print media advertising into marketing & advertising"),
    ("6150", "5600", "radio/tv advertising into marketing & advertising"),
    ("5830", "5540", "subscriptions & memberships into subscriptions"),
    ("fuel", "5110", "legacy text code normalized to Fuel"),
    ("FUEL", "5110", "legacy text code normalized to Fuel"),
    ("food", "5116", "legacy text code normalized to client amenities"),
]

MANUAL_REVIEW_CODES = ["5750", "5260", "1030", "1300", "5910", "6210", "COOP HGC"]


def q2(d: Decimal | None) -> Decimal:
    return d if d is not None else Decimal("0")


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(r"l:\limo\data\audit")
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / f"glcode_consolidation_dryrun_{stamp}.txt"
    csv_path = out_dir / f"glcode_consolidation_impacts_{stamp}.csv"
    apply_sql_path = out_dir / f"glcode_consolidation_apply_{stamp}.sql"
    rollback_sql_path = out_dir / f"glcode_consolidation_rollback_{stamp}.sql"

    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    lines: list[str] = []
    lines.append("GL CODE CONSOLIDATION DRY-RUN")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")

    # Gather impact per mapping per column.
    impact_rows: list[dict] = []

    for old_code, new_code, reason in REMAP:
        for column in ("gl_account_code", "gl_code"):
            cur.execute(
                f"""
                SELECT
                    %s::text AS old_code,
                    %s::text AS new_code,
                    %s::text AS column_name,
                    COUNT(*)::int AS row_count,
                    COALESCE(SUM(gross_amount),0)::numeric(14,2) AS gross_total
                FROM receipts
                WHERE COALESCE(TRIM({column}), '') = %s
                """,
                (old_code, new_code, column, old_code),
            )
            impact_rows.append(cur.fetchone())

    # Manual review code usage.
    manual_rows: list[dict] = []
    for code in MANUAL_REVIEW_CODES:
        for column in ("gl_account_code", "gl_code"):
            cur.execute(
                f"""
                SELECT
                    %s::text AS code,
                    %s::text AS column_name,
                    COUNT(*)::int AS row_count,
                    COALESCE(SUM(gross_amount),0)::numeric(14,2) AS gross_total
                FROM receipts
                WHERE COALESCE(TRIM({column}), '') = %s
                """,
                (code, column, code),
            )
            manual_rows.append(cur.fetchone())

    # Summary counts.
    total_rows_touched = sum(r["row_count"] for r in impact_rows)
    total_gross_touched = sum(q2(r["gross_total"]) for r in impact_rows)

    lines.append("Proposed remap impact (all rows, both GL columns):")
    lines.append(f"  rows_touched_total={total_rows_touched}")
    lines.append(f"  gross_total_touched={total_gross_touched}")
    lines.append("")

    lines.append("Per mapping / column:")
    for r in sorted(impact_rows, key=lambda x: (x["old_code"], x["column_name"])):
        lines.append(
            f"  {r['old_code']} -> {r['new_code']} [{r['column_name']}]: "
            f"rows={r['row_count']}, gross={q2(r['gross_total'])}"
        )

    lines.append("")
    lines.append("Manual review codes (not auto-remapped):")
    for r in sorted(manual_rows, key=lambda x: (x["code"], x["column_name"])):
        if r["row_count"] > 0:
            lines.append(
                f"  {r['code']} [{r['column_name']}]: rows={r['row_count']}, gross={q2(r['gross_total'])}"
            )

    # CSV export
    with csv_path.open("w", encoding="ascii", newline="") as f:
        f.write("old_code,new_code,column_name,row_count,gross_total\n")
        for r in sorted(impact_rows, key=lambda x: (x["old_code"], x["new_code"], x["column_name"])):
            f.write(
                f"{r['old_code']},{r['new_code']},{r['column_name']},{r['row_count']},{q2(r['gross_total'])}\n"
            )

    # Generate apply/rollback SQL with backup table.
    backup_table = f"glcode_remap_backup_{stamp}"

    apply_sql: list[str] = []
    apply_sql.append("-- DRY-RUN OUTPUT: REVIEW BEFORE EXECUTION")
    apply_sql.append("BEGIN;")
    apply_sql.append(f"CREATE TABLE IF NOT EXISTS {backup_table} (")
    apply_sql.append("  receipt_id bigint PRIMARY KEY,")
    apply_sql.append("  old_gl_account_code text,")
    apply_sql.append("  old_gl_code text,")
    apply_sql.append("  captured_at timestamp default now()")
    apply_sql.append(");")
    apply_sql.append("")
    apply_sql.append("-- Capture only affected rows once")
    where_parts = []
    for old_code, _, _ in REMAP:
        safe_old = old_code.replace("'", "''")
        where_parts.append(f"COALESCE(TRIM(gl_account_code),'') = '{safe_old}'")
        where_parts.append(f"COALESCE(TRIM(gl_code),'') = '{safe_old}'")
    where_sql = " OR ".join(where_parts)
    apply_sql.append(
        f"INSERT INTO {backup_table} (receipt_id, old_gl_account_code, old_gl_code)\n"
        f"SELECT receipt_id, gl_account_code, gl_code\n"
        f"FROM receipts\n"
        f"WHERE {where_sql}\n"
        f"ON CONFLICT (receipt_id) DO NOTHING;"
    )
    apply_sql.append("")

    for old_code, new_code, reason in REMAP:
        safe_old = old_code.replace("'", "''")
        safe_new = new_code.replace("'", "''")
        apply_sql.append(f"-- {old_code} -> {new_code} : {reason}")
        apply_sql.append(
            "UPDATE receipts\n"
            f"SET gl_account_code = '{safe_new}'\n"
            f"WHERE COALESCE(TRIM(gl_account_code),'') = '{safe_old}';"
        )
        apply_sql.append(
            "UPDATE receipts\n"
            f"SET gl_code = '{safe_new}'\n"
            f"WHERE COALESCE(TRIM(gl_code),'') = '{safe_old}';"
        )
        apply_sql.append("")

    apply_sql.append("-- COMMIT only after validating post-update checks")
    apply_sql.append("-- COMMIT;")
    apply_sql.append("-- ROLLBACK;")

    rollback_sql: list[str] = []
    rollback_sql.append("-- Rollback script for corresponding apply file")
    rollback_sql.append("BEGIN;")
    rollback_sql.append(
        "UPDATE receipts r\n"
        "SET gl_account_code = b.old_gl_account_code,\n"
        "    gl_code = b.old_gl_code\n"
        f"FROM {backup_table} b\n"
        "WHERE r.receipt_id = b.receipt_id;"
    )
    rollback_sql.append("-- Optional cleanup after verified rollback")
    rollback_sql.append(f"-- DROP TABLE {backup_table};")
    rollback_sql.append("COMMIT;")

    apply_sql_path.write_text("\n".join(apply_sql) + "\n", encoding="ascii")
    rollback_sql_path.write_text("\n".join(rollback_sql) + "\n", encoding="ascii")
    report_path.write_text("\n".join(lines) + "\n", encoding="ascii")

    print(f"REPORT: {report_path}")
    print(f"IMPACT_CSV: {csv_path}")
    print(f"APPLY_SQL: {apply_sql_path}")
    print(f"ROLLBACK_SQL: {rollback_sql_path}")
    print(f"BACKUP_TABLE: {backup_table}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
