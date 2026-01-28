#!/usr/bin/env python3
"""
Import Square Capital activity CSVs into Postgres for reconciliation.
- Reads docs/P-55QV76-Square_Capital_Activity_*.csv
- Parses columns: Date (yy-mm-dd), Description, Amount ($, commas)
- Creates table square_capital_activity if missing
- Idempotent via row_hash unique key
"""
import os
import glob
import csv
import re
import hashlib
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Load env both from absolute workspace path (common in this repo) and CWD
load_dotenv('l:/limo/.env'); load_dotenv()

DOCS_GLOB = os.path.join('docs', 'P-55QV76-Square_Capital_Activity_*.csv')

DDL = """
CREATE TABLE IF NOT EXISTS square_capital_activity (
    id SERIAL PRIMARY KEY,
    activity_date DATE NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(12,2) NOT NULL,
    source_file TEXT NOT NULL,
    row_hash CHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(row_hash)
);
CREATE INDEX IF NOT EXISTS idx_sca_date ON square_capital_activity(activity_date);
CREATE INDEX IF NOT EXISTS idx_sca_desc ON square_capital_activity(description);
"""

def parse_amount(text: str) -> float:
    text = (text or '').strip().replace('$', '').replace(',', '')
    if not text:
        return 0.0
    return float(text)

def parse_date(yy_mm_dd: str) -> datetime.date:
    # CSV uses '25-09-29' meaning 2025-09-29
    m = re.match(r'^(\d{2})-(\d{2})-(\d{2})$', (yy_mm_dd or '').strip())
    if not m:
        raise ValueError(f"Unexpected date format: {yy_mm_dd}")
    return datetime.strptime('20' + yy_mm_dd, '%Y-%m-%d').date()

def row_hash(activity_date, description, amount, source_file) -> str:
    s = f"{activity_date}|{description}|{amount:.2f}|{os.path.basename(source_file)}"
    return hashlib.md5(s.encode('utf-8')).hexdigest()

def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()

def collect_rows(file_path: str):
    inserted_rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            try:
                dt = parse_date(row['Date'])
                desc = (row['Description'] or '').strip()
                amt = parse_amount(row['Amount'])
                h = row_hash(dt, desc, amt, file_path)
                inserted_rows.append((dt, desc, amt, os.path.basename(file_path), h))
            except Exception as e:
                print(f"Skip row {i} in {file_path}: {e} -> {row}")
                continue
    return inserted_rows

def bulk_insert(conn, rows):
    if not rows:
        return 0, 0
    with conn.cursor() as cur:
        # Use RETURNING to reliably count inserted rows
        execute_values(
            cur,
            """
            INSERT INTO square_capital_activity (activity_date, description, amount, source_file, row_hash)
            VALUES %s
            ON CONFLICT (row_hash) DO NOTHING
            RETURNING row_hash
            """,
            rows,
            page_size=1000
        )
        returned = cur.fetchall()
        inserted = len(returned)
    conn.commit()
    return inserted, len(rows) - inserted

def main():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    try:
        ensure_schema(conn)
        files = sorted(glob.glob(DOCS_GLOB))
        if not files:
            print(f"No files matched pattern: {DOCS_GLOB}")
            return
        total_new = 0
        total_existing = 0
        all_rows = 0
        for fp in files:
            rows = collect_rows(fp)
            all_rows += len(rows)
            present, skipped = bulk_insert(conn, rows)
            total_new += present
            total_existing += skipped
            print(f"Imported from {os.path.basename(fp)}: {present} new, {skipped} duplicates (rows parsed: {len(rows)})")
        print(f"\nSummary: {total_new} inserted, {total_existing} duplicates across {len(files)} file(s), {all_rows} rows parsed.")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
