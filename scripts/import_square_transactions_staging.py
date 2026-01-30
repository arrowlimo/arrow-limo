"""
Import Square Transactions CSVs (2014–2015 discovered) into a staging table.

Scans paths like:
  - l:/limo/**/COMPLETE-AUDIT-TRAIL/square payments/transactions-*.csv

Normalizes common Square CSV headers and inserts into square_transactions_staging with
an idempotent hash.

Output summary: reports/square_transactions_staging_summary.md
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import psycopg2
import shutil
from datetime import datetime


ROOT = Path('l:/limo')
REPORTS = ROOT / 'reports'
REPORTS.mkdir(parents=True, exist_ok=True)


def get_db_connection():
    import os
    host = os.getenv('DB_HOST', 'localhost')
    dbname = os.getenv('DB_NAME', 'almsdata')
    user = os.getenv('DB_USER', 'postgres')
    password = os.getenv('DB_PASSWORD', '***REDACTED***')
    return psycopg2.connect(host=host, dbname=dbname, user=user, password=password)


def ensure_table(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS square_transactions_staging (
            id SERIAL PRIMARY KEY,
            source_file TEXT NOT NULL,
            row_no INTEGER NOT NULL,
            txn_date DATE NULL,
            gross_amount NUMERIC(14,2) NULL,
            fees_amount NUMERIC(14,2) NULL,
            tax_amount NUMERIC(14,2) NULL,
            net_amount NUMERIC(14,2) NULL,
            description TEXT NULL,
            raw_json TEXT NULL,
            content_sha256 TEXT NOT NULL UNIQUE,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


HEADER_MAP = {
    'date': 'date',
    'transaction date': 'date',
    'time': 'time',
    'timezone': 'timezone',
    'description': 'description',
    'amount': 'gross',
    'gross': 'gross',
    'total collected': 'gross',
    'fees': 'fees',
    'taxes': 'tax',
    'tax': 'tax',
    'net': 'net',
}


def norm_headers(headers):
    out = []
    for h in headers:
        key = (h or '').strip().lower()
        out.append(HEADER_MAP.get(key, key))
    return out


def parse_amount(val: Optional[str]) -> Optional[float]:
    if val is None:
        return None
    s = str(val).strip().replace(',', '').replace('$', '')
    if s == '':
        return None
    try:
        return float(s)
    except Exception:
        return None


def parse_date(d: Optional[str]) -> Optional[datetime]:
    if not d:
        return None
    d = d.strip()
    fmt_candidates = ['%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d']
    for fmt in fmt_candidates:
        try:
            return datetime.strptime(d, fmt)
        except Exception:
            continue
    return None


def import_csv(cur, path: Path) -> Tuple[int, int]:
    inserted = 0
    scanned = 0
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        headers = norm_headers(headers)
        for i, row in enumerate(reader, start=2):
            scanned += 1
            row_map: Dict[str, str] = {}
            for idx, val in enumerate(row):
                key = headers[idx] if idx < len(headers) else f'col{idx}'
                row_map[key] = val

            txn_date = parse_date(row_map.get('date'))
            gross = parse_amount(row_map.get('gross'))
            fees = parse_amount(row_map.get('fees'))
            tax = parse_amount(row_map.get('tax'))
            net = parse_amount(row_map.get('net'))
            desc = (row_map.get('description') or '').strip() or None

            raw_json = str(row_map)
            key_material = f"{path.name}|{i}|{row_map}".encode('utf-8', errors='ignore')
            content_sha256 = hashlib.sha256(key_material).hexdigest()

            cur.execute(
                """
                INSERT INTO square_transactions_staging
                (source_file, row_no, txn_date, gross_amount, fees_amount, tax_amount, net_amount, description, raw_json, content_sha256)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (content_sha256) DO NOTHING
                RETURNING id
                """,
                (
                    str(path), i,
                    txn_date.date() if txn_date else None,
                    gross, fees, tax, net, desc, raw_json, content_sha256
                )
            )
            if cur.rowcount:
                inserted += 1
    return scanned, inserted


def summarize(cur) -> str:
    cur.execute("SELECT COUNT(*), MIN(txn_date), MAX(txn_date) FROM square_transactions_staging")
    total, min_d, max_d = cur.fetchone()
    cur.execute(
        """
        SELECT EXTRACT(YEAR FROM txn_date)::int AS y, COUNT(*)
        FROM square_transactions_staging
        WHERE txn_date IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """
    )
    rows = cur.fetchall()
    lines = [
        '# Square Transactions Staging Summary',
        f'- Total rows: {total:,}',
        f'- Date span: {min_d} → {max_d}',
        '## By Year',
    ]
    for y, c in rows:
        lines.append(f'- {y}: {c:,}')
    return '\n'.join(lines) + '\n'


def main():
    # Discover CSVs
    candidates = list(ROOT.glob('**/COMPLETE-AUDIT-TRAIL/square payments/transactions-*.csv'))
    if not candidates:
        print('No Square transactions CSVs found')
        return

    conn = get_db_connection(); cur = conn.cursor()
    ensure_table(cur)
    conn.commit()

    total_scanned = total_inserted = 0
    moved = []
    for p in candidates:
        scanned, inserted = import_csv(cur, p)
        total_scanned += scanned
        total_inserted += inserted
        conn.commit()
        print(f'{p.name}: scanned {scanned:,}, inserted {inserted:,}')
        # Archive/move processed CSV next to its folder
        dest_dir = p.parent / 'already_imported'
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / p.name
        if dest.exists():
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            dest = dest_dir / f"{p.stem}__{ts}{p.suffix}"
        shutil.move(str(p), str(dest))
        moved.append(dest)

    s = summarize(cur)
    (REPORTS / 'square_transactions_staging_summary.md').write_text(s, encoding='utf-8')
    print(s)

    cur.close(); conn.close()
    print(f'Done. Total scanned: {total_scanned:,}, inserted: {total_inserted:,}')
    if moved:
        print('Moved files:')
        for m in moved:
            print(f'- {m}')


if __name__ == '__main__':
    main()
