#!/usr/bin/env python
r"""
Receipt de-duplication helper

Features:
- Delete a specific receipt_id (with safe fallback to soft-void when hard delete is blocked)
- Scan and report potential duplicates:
  * Multiple receipts linked to the same bank_id
  * Multiple receipts referencing the same bank txn id in source_reference (e.g., BTX_12345 / OFFICE_UTIL_12345)
  * Duplicate (receipt_date, amount) pairs (optionally filtered to Utilities/Rent)

PROTECTION: This script includes safeguards to prevent deletion from critical tables.

Usage examples:
  python -X utf8 scripts/dedupe_receipts.py --delete-id 78318
  python -X utf8 scripts/dedupe_receipts.py --scan --limit 50 --details

Environment:
  Uses DB_* env vars (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Any

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql

# Import protection safeguards
try:
    from table_protection import protect_deletion, create_backup_before_delete, log_deletion_audit
except ImportError:
    # Fallback if table_protection not available
    def protect_deletion(table_name, dry_run=True, override_key=None):
        if table_name in ('journal', 'receipts', 'payments', 'charters', 'clients', 'employees'):
            if not dry_run and not override_key:
                raise Exception(f"🛑 PROTECTED: Cannot delete from {table_name} without --override-key")
    def create_backup_before_delete(cur, table_name, condition=None):
        return None
    def log_deletion_audit(table_name, row_count, condition=None, script_name=None):
        pass


def get_conn():
    host = os.getenv("DB_HOST", "localhost")
    name = os.getenv("DB_NAME", "almsdata")
    user = os.getenv("DB_USER", os.getenv("POSTGRES_USER", "postgres"))
    pwd = os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD"))
    port = os.getenv("DB_PORT", "5432")
    if not pwd:
        # Allow passwordless if local trust, else fail clearly
        sys.stderr.write("[warn] DB_PASSWORD not set; relying on local trust or .pgpass.\n")
    return psycopg2.connect(host=host, dbname=name, user=user, password=pwd, port=port)


def get_table_columns(conn, table_name: str) -> Dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        return {r[0]: r[1] for r in cur.fetchall()}


def find_id_column(columns: Dict[str, str]) -> str:
    """Find the identifier column for receipts table.
    Tries common options in order.
    """
    for cand in ("receipt_id", "rc_id", "id"):
        if cand in columns:
            return cand
    # Fallback to first integer-like column name containing 'id'
    for name, dtype in columns.items():
        if "id" in name:
            return name
    # As a last resort, use 'receipt_id' (will likely fail but explicit)
    return "receipt_id"


def backup_receipt_row(conn, id_col: str, rec_id: int, dest_dir: str = "backups/receipts") -> Tuple[bool, str]:
    """Write the current receipt row to a JSON file for audit backup."""
    import json
    os.makedirs(dest_dir, exist_ok=True)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql.SQL("SELECT * FROM receipts WHERE {} = %s").format(sql.Identifier(id_col)), (rec_id,))
        row = cur.fetchone()
        if not row:
            return False, f"No row found for {id_col}={rec_id} to backup"
        # Filename includes id and timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(dest_dir, f"receipt_{rec_id}_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(row, f, ensure_ascii=False, indent=2, default=str)
        return True, f"Row backup written to {path}"


def try_delete_receipt(conn, receipt_id: int, columns: Dict[str, str]) -> Tuple[bool, str]:
    """Attempt hard delete; on FK violation, attempt a soft-void fallback.

    Returns (success, message)
    
    PROTECTION: Checks table protection before deletion.
    """
    # Apply protection check
    try:
        protect_deletion('receipts', dry_run=False)
    except Exception as e:
        return False, str(e)
    
    id_col = find_id_column(columns)
    try:
        with conn.cursor() as cur:
            # Backup first for audit
            ok_bk, msg_bk = backup_receipt_row(conn, id_col, receipt_id)
            if ok_bk:
                sys.stdout.write(f"[backup] {msg_bk}\n")
            else:
                sys.stdout.write(f"[backup-warn] {msg_bk}\n")

            cur.execute(
                sql.SQL("DELETE FROM receipts WHERE {} = %s RETURNING {} ").format(
                    sql.Identifier(id_col), sql.Identifier(id_col)
                ),
                (receipt_id,),
            )
            row = cur.fetchone()
        conn.commit()
        if row:
            # Log the deletion
            log_deletion_audit('receipts', 1, condition=f"{id_col}={receipt_id}", script_name='dedupe_receipts.py')
            return True, f"Hard-deleted receipt_id={receipt_id}"
        return False, f"No receipt found with receipt_id={receipt_id}"
    except psycopg2.Error as e:
        # Fallback: soft-void via available flag/notes
        conn.rollback()
        now = datetime.now().isoformat(timespec='seconds')
        flags = [c for c in ("is_deleted", "deleted", "voided", "is_void") if c in columns]
        notes_col = "notes" if "notes" in columns else None
        updates = []
        params: List[Any] = []
        for f in flags:
            updates.append(sql.SQL("{} = TRUE").format(sql.Identifier(f)))
        if notes_col:
            updates.append(sql.SQL("{} = COALESCE({}, '') || %s").format(sql.Identifier(notes_col), sql.Identifier(notes_col)))
            params.append(f" [AUTO-VOID {now}]: duplicate archived (kept canonical)")

        if not updates:
            # Last resort: just annotate vendor_name to mark duplicate (no totals changed)
            if "vendor_name" in columns:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            sql.SQL("""
                                UPDATE receipts
                                SET {vendor} = {vendor} || %s
                                WHERE {id_col} = %s
                            """).format(vendor=sql.Identifier("vendor_name"), id_col=sql.Identifier(id_col)),
                            (" [DUPLICATE - IGNORE]", receipt_id),
                        )
                    conn.commit()
                    return True, (
                        f"Hard delete blocked ({type(e).__name__}); marked receipt_id={receipt_id} vendor_name with '[DUPLICATE - IGNORE]'"
                    )
                except psycopg2.Error as e2:
                    conn.rollback()
                    return False, f"Failed to annotate duplicate (receipt_id={receipt_id}): {e2.pgerror or e2}"
            return False, f"Hard delete blocked and no soft-void columns available: {e.pgerror or e}"

        try:
            with conn.cursor() as cur:
                query = sql.SQL("UPDATE receipts SET {} WHERE {} = %s").format(
                    sql.SQL(", ").join(updates), sql.Identifier(id_col)
                )
                cur.execute(query, (*params, receipt_id))
            conn.commit()
            return True, f"Hard delete blocked ({type(e).__name__}); soft-voided receipt_id={receipt_id}"
        except psycopg2.Error as e3:
            conn.rollback()
            return False, f"Soft-void update failed for receipt_id={receipt_id}: {e3.pgerror or e3}"


def scan_duplicates(conn, limit: int = 50, details: bool = False) -> Dict[str, Any]:
    cols = get_table_columns(conn, "receipts")
    id_col = find_id_column(cols)
    results: Dict[str, Any] = {}

    # bank_id duplicates
    if "bank_id" in cols:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT bank_id, COUNT(*) AS cnt,
                           ARRAY_AGG({id} ORDER BY {id}) AS receipt_ids
                    FROM receipts
                    WHERE bank_id IS NOT NULL
                    GROUP BY bank_id
                    HAVING COUNT(*) > 1
                    ORDER BY cnt DESC, bank_id DESC
                    LIMIT %s
                    """
                ).format(id=sql.Identifier(id_col)),
                (limit,),
            )
            rows = cur.fetchall()
        results["duplicates_by_bank_id"] = rows

        # Optionally pull details
        if details and rows:
            ids = []
            for r in rows:
                ids.extend(r["receipt_ids"])  # type: ignore[index]
            if ids:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    fields = [id_col, "bank_id"]
                    for c in ("vendor_name", "category", "receipt_date", "gross_amount", "amount", "gst_amount", "created_at", "source_reference"):
                        if c in cols and c not in fields:
                            fields.append(c)
                    q = sql.SQL("SELECT {} FROM receipts WHERE {} = ANY(%s) ORDER BY bank_id, receipt_date NULLS LAST, {} ").format(
                        sql.SQL(", ").join(map(sql.Identifier, fields))
                    , sql.Identifier(id_col), sql.Identifier(id_col))
                    cur.execute(q, (ids,))
                    results["duplicates_by_bank_id_details"] = cur.fetchall()

    # source_reference duplicates by trailing digits (likely bank txn id embedded)
    if "source_reference" in cols:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                sql.SQL(
                    """
                    SELECT (regexp_matches(source_reference, '(\d+)$'))[1]::bigint AS ref_id,
                           COUNT(*) AS cnt,
                           ARRAY_AGG({id} ORDER BY {id}) AS receipt_ids
                    FROM receipts
                    WHERE source_reference ~ '(\d+)$'
                    GROUP BY 1
                    HAVING COUNT(*) > 1
                    ORDER BY cnt DESC, ref_id DESC
                    LIMIT %s
                    """
                ).format(id=sql.Identifier(id_col)),
                (limit,),
            )
            results["duplicates_by_source_reference_id"] = cur.fetchall()

    # amount/date duplicates (prefer Utilities/Rent when category exists)
    amt_col = "gross_amount" if "gross_amount" in cols else ("amount" if "amount" in cols else None)
    if amt_col and "receipt_date" in cols:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if "category" in cols:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT receipt_date, {amt} AS amount, COUNT(*) AS cnt,
                               ARRAY_AGG({id} ORDER BY {id}) AS receipt_ids
                        FROM receipts
                        WHERE category ILIKE ANY(ARRAY['%Utilities%','%Rent%'])
                        GROUP BY 1, 2
                        HAVING COUNT(*) > 1
                        ORDER BY cnt DESC, receipt_date DESC
                        LIMIT %s
                        """
                    ).format(amt=sql.Identifier(amt_col), id=sql.Identifier(id_col)),
                    (limit,),
                )
            else:
                cur.execute(
                    sql.SQL(
                        """
                        SELECT receipt_date, {amt} AS amount, COUNT(*) AS cnt,
                               ARRAY_AGG({id} ORDER BY {id}) AS receipt_ids
                        FROM receipts
                        GROUP BY 1, 2
                        HAVING COUNT(*) > 1
                        ORDER BY cnt DESC, receipt_date DESC
                        LIMIT %s
                        """
                    ).format(amt=sql.Identifier(amt_col), id=sql.Identifier(id_col)),
                    (limit,),
                )
            rows = cur.fetchall()
            results["duplicates_by_date_amount"] = rows

            if details and rows:
                ids = []
                for r in rows:
                    ids.extend(r["receipt_ids"])  # type: ignore[index]
                if ids:
                    with conn.cursor(cursor_factory=RealDictCursor) as dcur:
                        fields = [id_col, "receipt_date"]
                        for c in (amt_col, "vendor_name", "category", "bank_id", "gst_amount", "source_reference", "created_at"):
                            if c in cols and c not in fields:
                                fields.append(c)
                        q = sql.SQL("SELECT {} FROM receipts WHERE {} = ANY(%s) ORDER BY receipt_date DESC, {} ").format(
                            sql.SQL(", ").join(map(sql.Identifier, fields)), sql.Identifier(id_col), sql.Identifier(id_col)
                        )
                        dcur.execute(q, (ids,))
                        results["duplicates_by_date_amount_details"] = dcur.fetchall()

    return results


def main():
    ap = argparse.ArgumentParser(description="Delete specific receipt and/or scan for duplicate receipts")
    ap.add_argument("--delete-id", type=int, help="receipt_id to delete (older duplicate)")
    ap.add_argument("--scan", action="store_true", help="Scan and print potential duplicates")
    ap.add_argument("--limit", type=int, default=50, help="Limit for duplicate result groups")
    ap.add_argument("--details", action="store_true", help="Include detailed rows for duplicates")
    args = ap.parse_args()

    conn = get_conn()
    try:
        cols = get_table_columns(conn, "receipts")
        if args.delete_id is not None:
            ok, msg = try_delete_receipt(conn, args.delete_id, cols)
            print(("SUCCESS: " if ok else "ERROR: ") + msg)

        if args.scan:
            report = scan_duplicates(conn, limit=args.limit, details=args.details)
            # Compact summary
            print("\nDuplicate scan summary:")
            for k, v in report.items():
                if isinstance(v, list):
                    print(f"- {k}: {len(v)} group(s)")
                else:
                    print(f"- {k}: {type(v).__name__}")

            # Pretty print some top entries
            def preview(label: str, rows: List[Dict[str, Any]], max_rows: int = 10):
                if not rows:
                    print(f"\n{label}: none")
                    return
                print(f"\n{label}: showing up to {min(max_rows, len(rows))} groups")
                for r in rows[:max_rows]:
                    print(r)

            preview("duplicates_by_bank_id", report.get("duplicates_by_bank_id", []))
            preview("duplicates_by_source_reference_id", report.get("duplicates_by_source_reference_id", []))
            preview("duplicates_by_date_amount", report.get("duplicates_by_date_amount", []))

    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
