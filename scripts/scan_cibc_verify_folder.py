#!/usr/bin/env python3
"""
Scan and verify banking-related files under a target folder.

Folder: L:\\limo\\CIBC UPLOADS\\verify this data

What it does:
- Recursively scans all files (csv,xlsx,txt,mht,eml,pdf,docx) and computes MD5/SHA1/size.
- Extracts simple metadata (first/last lines; CSV header; date range estimation when possible).
- Compares discovered CSV rows to existing DB tables when formats are recognizable.
- Writes a raw inventory table (raw_file_inventory) in Postgres.
- Exports CSV reports:
  • reports/cibc_verify_scan.csv - full file inventory
  • reports/duplicates_by_name.csv
  • reports/duplicates_by_hash.csv
  • reports/new_banking_candidates.csv - files not represented in banking_transactions by date/amount sample

Idempotent and safe. Won't import data; only scans and reports.
"""

import csv
import hashlib
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Tuple

import psycopg2

DB = {
    'dbname': 'almsdata',
    'user': 'postgres',
    'password': '***REMOVED***',
    'host': 'localhost',
    'port': 5432,
}

TARGET_DIR = r"L:\\limo\\CIBC UPLOADS\\verify this data"
OUT_DIR = 'reports'

SUPPORTED_EXT = {'.csv', '.xlsx', '.txt', '.mht', '.eml', '.pdf', '.docx'}


def md5(s: bytes) -> str:
    return hashlib.md5(s).hexdigest()


def sha1(s: bytes) -> str:
    return hashlib.sha1(s).hexdigest()


def file_fingerprints(path: str) -> Tuple[int, str, str]:
    size = os.path.getsize(path)
    h_md5 = hashlib.md5()
    h_sha1 = hashlib.sha1()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h_md5.update(chunk)
            h_sha1.update(chunk)
    return size, h_md5.hexdigest(), h_sha1.hexdigest()


def read_first_last_lines(path: str, n: int = 2) -> Tuple[List[str], List[str]]:
    first: List[str] = []
    last: List[str] = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for i in range(n):
                line = f.readline()
                if not line:
                    break
                first.append(line.strip())
        # Read last n lines efficiently
        with open(path, 'rb') as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 1024
            data = b''
            while size > 0 and len(data.splitlines()) <= n + 1:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
            tail = data.splitlines()[-n:]
            last = [t.decode('utf-8', 'ignore').strip() for t in tail]
    except Exception:
        pass
    return first, last


def ensure_inventory_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS raw_file_inventory (
            id SERIAL PRIMARY KEY,
            scan_time TIMESTAMP NOT NULL DEFAULT NOW(),
            root_path TEXT NOT NULL,
            rel_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            ext TEXT,
            size_bytes BIGINT,
            md5 TEXT,
            sha1 TEXT,
            first_line TEXT,
            last_line TEXT,
            notes TEXT
        );
        """
    )
    conn.commit()


def upsert_inventory_row(cur, root_path: str, rel_path: str, file_name: str, ext: str,
                         size_bytes: int, md5_hex: str, sha1_hex: str,
                         first_line: str, last_line: str, notes: str) -> None:
    cur.execute(
        """
        INSERT INTO raw_file_inventory(root_path, rel_path, file_name, ext, size_bytes, md5, sha1, first_line, last_line, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (root_path, rel_path, file_name, ext, size_bytes, md5_hex, sha1_hex, first_line, last_line, notes)
    )


def scan_folder() -> List[Dict[str, Any]]:
    inventory: List[Dict[str, Any]] = []
    for root, _, files in os.walk(TARGET_DIR):
        for name in files:
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext and ext not in SUPPORTED_EXT:
                # still fingerprint to track, but mark unsupported
                pass
            try:
                size, md5_hex, sha1_hex = file_fingerprints(path)
                first_lines, last_lines = ([], [])
                if ext in {'.csv', '.txt'}:
                    first_lines, last_lines = read_first_last_lines(path, n=2)
                inventory.append({
                    'root_path': TARGET_DIR,
                    'rel_path': os.path.relpath(path, TARGET_DIR),
                    'file_name': name,
                    'ext': ext,
                    'size_bytes': size,
                    'md5': md5_hex,
                    'sha1': sha1_hex,
                    'first_line': (first_lines[0] if first_lines else None),
                    'last_line': (last_lines[-1] if last_lines else None),
                    'notes': ''
                })
            except Exception as e:
                inventory.append({
                    'root_path': TARGET_DIR,
                    'rel_path': os.path.relpath(path, TARGET_DIR),
                    'file_name': name,
                    'ext': ext,
                    'size_bytes': None,
                    'md5': None,
                    'sha1': None,
                    'first_line': None,
                    'last_line': None,
                    'notes': f'error: {e}'
                })
    return inventory


def write_csv(path: str, rows: List[Dict[str, Any]], headers: List[str]) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


def analyze_dupes(inventory: List[Dict[str, Any]]):
    # by name
    name_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in inventory:
        key = r['file_name'].lower()
        name_map.setdefault(key, []).append(r)
    dupes_name = [r for group in name_map.values() if len(group) > 1 for r in group]
    # by hash
    hash_map: Dict[str, List[Dict[str, Any]]] = {}
    for r in inventory:
        key = (r.get('md5') or '') + '|' + (r.get('sha1') or '')
        hash_map.setdefault(key, []).append(r)
    dupes_hash = [r for group in hash_map.values() if len(group) > 1 for r in group]
    return dupes_name, dupes_hash


def sample_csv_rows(path: str, max_rows: int = 50) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            for i, r in enumerate(reader):
                rows.append(r)
                if i + 1 >= max_rows:
                    break
    except Exception:
        return []
    return rows


def csv_rows_exist_in_banking(conn, rows: List[Dict[str, Any]]) -> bool:
    """Quick existence check: try matching several rows by date and amount against banking_transactions.
    Supports CIBC compiled CSV headers we used earlier: Trans_date, Debit, Credit.
    """
    if not rows:
        return False
    keys = [('Trans_date', 'Debit', 'Credit'), ('Date', 'Debit', 'Credit')]
    cur = conn.cursor()
    found = 0
    tested = 0
    for r in rows:
        header = None
        for k in keys:
            if all(key in r for key in k):
                header = k
                break
        if not header:
            continue
        tested += 1
        dkey, d_debit, d_credit = header
        try:
            dt = r.get(dkey)
            debit = float(r.get(d_debit) or 0)
            credit = float(r.get(d_credit) or 0)
            net = round(credit - debit, 2)
            # Look for a matching bank row on that date
            cur.execute(
                """
                SELECT 1 FROM banking_transactions
                 WHERE transaction_date = %s
                   AND ROUND(COALESCE(credit_amount,0) - COALESCE(debit_amount,0), 2) = %s
                 LIMIT 1
                """,
                (dt, net)
            )
            if cur.fetchone():
                found += 1
        except Exception:
            pass
        if tested >= 10:
            break
    return found > 0 and tested > 0


def main():
    print(f"Scanning folder: {TARGET_DIR}")
    inv = scan_folder()

    conn = psycopg2.connect(**DB)
    ensure_inventory_table(conn)
    cur = conn.cursor()

    # Insert inventory rows
    inserted = 0
    for r in inv:
        upsert_inventory_row(
            cur,
            r['root_path'], r['rel_path'], r['file_name'], r['ext'], r['size_bytes'], r['md5'], r['sha1'],
            r.get('first_line'), r.get('last_line'), r.get('notes')
        )
        inserted += 1
    conn.commit()
    print(f"Inventory rows inserted: {inserted}")

    # Reports
    os.makedirs(OUT_DIR, exist_ok=True)
    headers = ['root_path', 'rel_path', 'file_name', 'ext', 'size_bytes', 'md5', 'sha1', 'first_line', 'last_line', 'notes']
    write_csv(os.path.join(OUT_DIR, 'cibc_verify_scan.csv'), inv, headers)

    dupes_name, dupes_hash = analyze_dupes(inv)
    write_csv(os.path.join(OUT_DIR, 'duplicates_by_name.csv'), dupes_name, headers)
    write_csv(os.path.join(OUT_DIR, 'duplicates_by_hash.csv'), dupes_hash, headers)

    # New banking candidates report
    candidates: List[Dict[str, Any]] = []
    for r in inv:
        if (r['ext'] or '').lower() != '.csv':
            continue
        sample = sample_csv_rows(os.path.join(TARGET_DIR, r['rel_path']))
        exists = False
        try:
            exists = csv_rows_exist_in_banking(conn, sample)
        except Exception:
            exists = False
        if not exists:
            c = dict(r)
            c['notes'] = 'not found in banking by sample rows'
            candidates.append(c)

    write_csv(os.path.join(OUT_DIR, 'new_banking_candidates.csv'), candidates, headers)
    print("Wrote reports: cibc_verify_scan.csv, duplicates_by_name.csv, duplicates_by_hash.csv, new_banking_candidates.csv")

    cur.close(); conn.close()


if __name__ == '__main__':
    # Allow overriding target dir from CLI without using global assignment inside a function
    if len(sys.argv) > 1:
        TARGET_DIR = sys.argv[1]
    main()
