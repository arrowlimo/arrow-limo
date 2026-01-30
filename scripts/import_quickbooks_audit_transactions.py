"""
Import QuickBooks CRA audit Transactions.xml files into a staging table.

- Scans: l:/limo/quickbooks/CRAauditexport__*__*.zip
- Reads: Transactions.xml (or any *.xml if missing)
- Heuristic parse: capture date tokens (YYYY-MM-DD or YYYY/MM/DD), a nearby amount if present,
  and store the raw line for later, with a deterministic content hash for idempotence.
  This provides immediate visibility of NEW data vs existing, without depending on
  a specific QB XML schema variant.

Writes:
- Table: qb_transactions_staging
  (id, source_zip, entry_name, line_no, txn_date, amount, description, raw_line, content_sha256, imported_at)

CLI:
  python -X utf8 scripts/import_quickbooks_audit_transactions.py --write
  python -X utf8 scripts/import_quickbooks_audit_transactions.py --limit 1000

Notes:
- Safe: writes only to a new staging table; uses ON CONFLICT DO NOTHING on content hash.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional, Tuple
from zipfile import ZipFile
import shutil
from datetime import datetime

import psycopg2


ROOT = Path('l:/limo')
QB_DIR = ROOT / 'quickbooks'
REPORTS_DIR = ROOT / 'reports'
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DATE_PATTERN = re.compile(r'(\d{4})[-/](\d{2})[-/](\d{2})')
AMOUNT_PATTERN = re.compile(r'([-+]?\d{1,3}(?:,\d{3})*(?:\.\d{2})|[-+]?\d+\.\d{2})')


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
        CREATE TABLE IF NOT EXISTS qb_transactions_staging (
            id SERIAL PRIMARY KEY,
            source_zip TEXT NOT NULL,
            entry_name TEXT NOT NULL,
            line_no INTEGER NOT NULL,
            txn_date DATE NULL,
            amount NUMERIC(14,2) NULL,
            description TEXT NULL,
            raw_line TEXT NOT NULL,
            content_sha256 TEXT NOT NULL UNIQUE,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def iter_xml_lines(zip_path: Path) -> Iterator[Tuple[str, int, str]]:
    with ZipFile(zip_path) as zf:
        names = zf.namelist()
        candidates = [n for n in names if n.lower().endswith('transactions.xml')]
        if not candidates:
            candidates = [n for n in names if n.lower().endswith('.xml')]
        for name in candidates:
            with zf.open(name, 'r') as f:
                for i, raw in enumerate(f, start=1):
                    try:
                        line = raw.decode('utf-8', errors='ignore')
                    except Exception:
                        continue
                    yield (name, i, line)


def parse_line(line: str) -> Tuple[Optional[datetime], Optional[float], Optional[str]]:
    # Date
    dmatch = DATE_PATTERN.search(line)
    txn_date = None
    if dmatch:
        y, m, d = map(int, dmatch.groups())
        if 1900 <= y <= 2100:
            try:
                txn_date = datetime(y, m, d)
            except Exception:
                txn_date = None

    # Amount (best-effort): choose the first amount-like token
    amt = None
    am = AMOUNT_PATTERN.search(line)
    if am:
        try:
            amt = float(am.group(1).replace(',', ''))
        except Exception:
            amt = None

    # Description (trimmed raw)
    desc = line.strip()
    if len(desc) > 500:
        desc = desc[:500]
    return txn_date, amt, desc


def import_zip(cur, zip_path: Path, limit: Optional[int] = None) -> Tuple[int, int]:
    inserted = 0
    scanned = 0
    for entry_name, line_no, line in iter_xml_lines(zip_path):
        scanned += 1
        if limit and scanned > limit:
            break
        txn_date, amount, desc = parse_line(line)
        key_material = f"{zip_path.name}|{entry_name}|{line_no}|{line}".encode('utf-8', errors='ignore')
        content_sha256 = hashlib.sha256(key_material).hexdigest()
        cur.execute(
            """
            INSERT INTO qb_transactions_staging
            (source_zip, entry_name, line_no, txn_date, amount, description, raw_line, content_sha256)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (content_sha256) DO NOTHING
            RETURNING id
            """,
            (
                zip_path.name,
                entry_name,
                line_no,
                txn_date.date() if txn_date else None,
                amount,
                desc,
                line,
                content_sha256,
            ),
        )
        if cur.rowcount:
            inserted += 1
    return scanned, inserted


def summarize(cur) -> str:
    cur.execute("SELECT COUNT(*), COALESCE(MIN(txn_date), NULL), COALESCE(MAX(txn_date), NULL) FROM qb_transactions_staging")
    total, min_d, max_d = cur.fetchone()
    cur.execute(
        """
        SELECT EXTRACT(YEAR FROM txn_date)::int AS y, COUNT(*)
        FROM qb_transactions_staging
        WHERE txn_date IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """
    )
    rows = cur.fetchall()
    lines = [
        '# QB Transactions Staging Summary',
        f'- Total rows: {total:,}',
        f'- Date span: {min_d} → {max_d}',
        '## By Year',
    ]
    for y, c in rows:
        lines.append(f'- {y}: {c:,}')
    return '\n'.join(lines) + '\n'


def safe_move(src: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest = dest_dir / f"{src.stem}__{ts}{src.suffix}"
    shutil.move(str(src), str(dest))
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='Apply inserts (default is dry-run)')
    ap.add_argument('--limit', type=int, help='Limit scanned lines per ZIP for quick tests')
    ap.add_argument('--no-archive', action='store_true', help='Do not move processed files to already_imported')
    args = ap.parse_args()

    zips = sorted(QB_DIR.glob('CRAauditexport__*_*.zip'))
    if not zips:
        print(f'No CRA audit export ZIPs found in {QB_DIR}')
        return

    conn = get_db_connection(); cur = conn.cursor()
    ensure_table(cur)
    if args.write:
        conn.commit()

    total_scanned = total_inserted = 0
    moved = []
    for zp in zips:
        scanned, inserted = import_zip(cur, zp, limit=args.limit)
        total_scanned += scanned
        total_inserted += inserted
        if args.write:
            conn.commit()
        print(f'{zp.name}: scanned {scanned:,}, inserted {inserted:,}')
        # Archive/move after successful processing
        if not args.no_archive:
            dest = safe_move(zp, QB_DIR / 'already_imported')
            moved.append(dest)

    # Write summary
    s = summarize(cur)
    (REPORTS_DIR / 'qb_transactions_staging_summary.md').write_text(s, encoding='utf-8')
    print(s)

    cur.close(); conn.close()
    print(f'Done. Total scanned: {total_scanned:,}, inserted: {total_inserted:,}')
    if moved:
        print('Moved files:')
        for p in moved:
            print(f'- {p}')


if __name__ == '__main__':
    main()
