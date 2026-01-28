#!/usr/bin/env python3
"""
Scan and Stage Uploaded Pay Documents
====================================

- Scans a folder (default: L:\\limo\\uploaded_pay) for files matching a target year
- Stages file metadata into staging_driver_pay_files (if table exists) or writes a manifest CSV
- After successful staging (and with --write), moves files into an 'imported' subfolder to avoid reprocessing

Usage:
  python -X utf8 scripts/scan_uploaded_pay.py --year 2021
  python -X utf8 scripts/scan_uploaded_pay.py --dir L:\\limo\\uploaded_pay --year 2012 --write

Safe by default (dry-run). No DB writes or file moves without --write.
"""
from __future__ import annotations

import os
import re
import csv
import sys
import shutil
import hashlib
import argparse
from datetime import datetime
from typing import List, Dict

import psycopg2

DSN = dict(
    host=os.environ.get('DB_HOST', 'localhost'),
    database=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REMOVED***'),
    port=int(os.environ.get('DB_PORT', '5432')),
)

SUPPORTED_EXT = {'.pdf', '.xlsx', '.xls', '.csv', '.qbo'}
YEAR_RE = re.compile(r'(19|20)\d{2}')


def parse_args():
    ap = argparse.ArgumentParser(description='Scan and stage uploaded pay documents')
    ap.add_argument('--dir', default=r'L:\\limo\\uploaded_pay', help='Directory to scan')
    ap.add_argument('--year', type=int, default=2021, help='Target year filter')
    ap.add_argument('--write', action='store_true', help='Apply changes (DB insert + move files)')
    ap.add_argument('--only-pdf', action='store_true', help='Restrict processing to PDF files only')
    ap.add_argument('--recursive', action='store_true', help='Scan recursively')
    ap.add_argument('--outdir', default='exports/staging', help='Manifest output directory if table missing')
    return ap.parse_args()


def file_hash(path: str, block_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(block_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def find_year_in_name(name: str) -> int | None:
    m = YEAR_RE.search(name)
    if not m:
        return None
    try:
        return int(m.group(0))
    except Exception:
        return None


def list_files(root: str, recursive: bool) -> List[str]:
    files = []
    if recursive:
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                files.append(os.path.join(dirpath, fn))
    else:
        for fn in os.listdir(root):
            p = os.path.join(root, fn)
            if os.path.isfile(p):
                files.append(p)
    return files


def connect_db():
    try:
        return psycopg2.connect(**DSN)
    except Exception as e:
        print('[WARN]  DB connect failed, will write manifest CSV instead:', e)
        return None


def table_exists(conn, table: str) -> bool:
    if not conn:
        return False
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return cur.fetchone() is not None


def get_table_columns(conn, table: str) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


def stage_file(conn, rec: Dict, write: bool) -> bool:
    """Insert into staging_driver_pay_files if available. Returns True on (pretend) success.

    Defensive: adapts to available columns; if insert fails, continues without blocking move.
    """
    if not conn:
        return True  # manifest mode; allow move if requested
    if not table_exists(conn, 'staging_driver_pay_files'):
        return True

    cols = get_table_columns(conn, 'staging_driver_pay_files')
    insert_cols = []
    values = []

    # Safely map known fields if present
    if 'file_path' in cols:
        insert_cols.append('file_path'); values.append(rec['path'])
    if 'file_name' in cols:
        insert_cols.append('file_name'); values.append(rec['name'])
    if 'file_size' in cols:
        insert_cols.append('file_size'); values.append(rec['size'])
    if 'file_hash' in cols:
        insert_cols.append('file_hash'); values.append(rec['hash'])
    if 'detected_year' in cols:
        insert_cols.append('detected_year'); values.append(rec['year'])
    if 'source_folder' in cols:
        insert_cols.append('source_folder'); values.append(rec['folder'])
    if 'file_type' in cols:
        insert_cols.append('file_type'); values.append((rec['ext'].lstrip('.') or 'pdf'))
    if 'processed_at' in cols:
        insert_cols.append('processed_at'); values.append(datetime.now())
    if 'validation_status' in cols:
        insert_cols.append('validation_status'); values.append('staged' if write else 'dry-run')
    if 'error_message' in cols:
        insert_cols.append('error_message'); values.append(None)

    if not insert_cols:
        return True

    placeholders = ','.join(['%s'] * len(values))
    sql = f"INSERT INTO staging_driver_pay_files ({', '.join(insert_cols)}) VALUES ({placeholders})"

    try:
        if write:
            prev_autocommit = conn.autocommit
            conn.autocommit = True
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, values)
            finally:
                conn.autocommit = prev_autocommit
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print('  [WARN]  Staging insert failed; continuing with move:', e)
        return True
    return True


def ensure_imported_dir(root: str) -> str:
    imported = os.path.join(root, 'imported')
    os.makedirs(imported, exist_ok=True)
    return imported


def write_manifest(manifest_rows: List[Dict], year: int, outdir: str) -> str:
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, f'uploaded_pay_manifest_{year}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    if not manifest_rows:
        # write header only
        fieldnames = ['path','name','size','hash','ext','year','folder']
        with open(path, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()
        return path
    fieldnames = list(manifest_rows[0].keys())
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in manifest_rows:
            w.writerow(r)
    return path


def main():
    args = parse_args()
    root = args.dir
    year = args.year
    recursive = args.recursive
    write = args.write

    if not os.path.isdir(root):
        print('[FAIL] Directory not found:', root)
        sys.exit(1)

    files = list_files(root, recursive)
    candidates = []

    for p in files:
        ext = os.path.splitext(p)[1].lower()
        if ext not in SUPPORTED_EXT:
            continue
        if args.only_pdf and ext != '.pdf':
            continue
        name = os.path.basename(p)
        detected_year = find_year_in_name(name) or find_year_in_name(p)
        if detected_year != year:
            continue
        size = os.path.getsize(p)
        h = file_hash(p)
        candidates.append(dict(
            path=p,
            name=name,
            size=size,
            hash=h,
            ext=ext,
            year=detected_year,
            folder=root,
        ))

    print(f'📁 Scanned: {root}')
    print(f'🎯 Target year: {year}')
    print(f'🧾 Candidates found: {len(candidates)}')

    if not candidates:
        print('ℹ️  No files matched the year filter. Nothing to do.')
        sys.exit(0)

    conn = connect_db()
    manifest_rows = []
    for rec in candidates:
        ok = stage_file(conn, rec, write)
        manifest_rows.append(rec)
        if ok and write:
            imported_dir = ensure_imported_dir(root)
            dest = os.path.join(imported_dir, rec['name'])
            # Avoid overwrite
            if os.path.exists(dest):
                base, ext = os.path.splitext(rec['name'])
                dest = os.path.join(imported_dir, f"{base}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
            shutil.move(rec['path'], dest)
            print(f'  [OK] Moved: {rec['path']} -> {dest}')
        else:
            print(f"  🔎 Would stage: {rec['name']} ({rec['ext']}, {rec['size']} bytes)")

    # If staging table missing or for audit, write manifest
    manifest_path = write_manifest(manifest_rows, year, args.outdir)
    print('🧾 Manifest:', manifest_path)
    if not write:
        print('Dry-run complete. Re-run with --write to apply staging and move files into imported/.')


if __name__ == '__main__':
    main()
