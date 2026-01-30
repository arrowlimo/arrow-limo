import os
import sys
import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Tuple

import psycopg2
import pandas as pd

# Connection settings
PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

QB_DIRS = [
    r"L:\\limo\\quickbooks",
    r"L:\\limo\\quickbooks\\New folder",
]

SUPPORTED_EXT = {'.csv', '.xlsx', '.xls', '.qbo'}  # PDFs are deferred to OCR later

@dataclass
class FileRecord:
    file_path: str
    file_name: str
    file_type: str
    source_hash: Optional[str]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )


def ensure_migration_ran(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS public.staging_driver_pay_files (
        id BIGSERIAL PRIMARY KEY,
        file_path TEXT NOT NULL UNIQUE,
        file_name TEXT NOT NULL,
        file_type TEXT NOT NULL,
        source_hash TEXT,
        rows_parsed INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        error_message TEXT,
        first_txn_date DATE,
        last_txn_date DATE,
        processed_at TIMESTAMPTZ DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS public.staging_driver_pay (
        id BIGSERIAL PRIMARY KEY,
        file_id BIGINT REFERENCES public.staging_driver_pay_files(id) ON DELETE CASCADE,
        source_row_id TEXT,
        source_line_no INTEGER,
        txn_date DATE,
        driver_name TEXT,
        driver_id TEXT,
        pay_type TEXT,
        gross_amount NUMERIC(14,2),
        expense_amount NUMERIC(14,2),
        net_amount NUMERIC(14,2),
        amount NUMERIC(14,2),
        currency TEXT DEFAULT 'CAD',
        memo TEXT,
        check_no TEXT,
        account TEXT,
        category TEXT,
        vendor TEXT,
        source_sheet TEXT,
        source_file TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        UNIQUE (file_id, COALESCE(source_row_id,''), COALESCE(source_line_no,0), COALESCE(txn_date,'1900-01-01'), COALESCE(amount,0), COALESCE(memo,''))
    );
    CREATE INDEX IF NOT EXISTS idx_sdp_txn_date ON public.staging_driver_pay(txn_date);
    CREATE INDEX IF NOT EXISTS idx_sdp_driver_name ON public.staging_driver_pay(driver_name);
    CREATE INDEX IF NOT EXISTS idx_sdp_file_id ON public.staging_driver_pay(file_id);
    CREATE TABLE IF NOT EXISTS public.staging_driver_pay_issues (
        id BIGSERIAL PRIMARY KEY,
        file_id BIGINT REFERENCES public.staging_driver_pay_files(id) ON DELETE CASCADE,
        row_id BIGINT REFERENCES public.staging_driver_pay(id) ON DELETE CASCADE,
        issue_type TEXT NOT NULL,
        issue_detail TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    );
    """)
    conn.commit()
    cur.close()


def upsert_file(conn, fr: FileRecord) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO public.staging_driver_pay_files (file_path, file_name, file_type, source_hash)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (file_path) DO UPDATE SET source_hash = EXCLUDED.source_hash, processed_at = now()
        RETURNING id
        """,
        (fr.file_path, fr.file_name, fr.file_type, fr.source_hash),
    )
    file_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return file_id


def mark_file_status(conn, file_id: int, status: str, rows: int = 0, err: Optional[str] = None, dates: Optional[Tuple[Optional[datetime], Optional[datetime]]] = None):
    cur = conn.cursor()
    first_date = dates[0].date() if dates and dates[0] else None
    last_date = dates[1].date() if dates and dates[1] else None
    cur.execute(
        """
        UPDATE public.staging_driver_pay_files
        SET status = %s, rows_parsed = %s, error_message = %s, first_txn_date = %s, last_txn_date = %s, processed_at = now()
        WHERE id = %s
        """,
        (status, rows, err, first_date, last_date, file_id),
    )
    conn.commit()
    cur.close()


def parse_qbo(path: Path) -> pd.DataFrame:
    # .qbo is OFX; try pandas read_xml; fallback to manual parse
    try:
        df = pd.read_xml(path, xpath='//STMTTRN')
        # Normalize columns
        df = df.rename(columns={
            'DTPOSTED': 'txn_date',
            'TRNAMT': 'amount',
            'NAME': 'memo',
            'FITID': 'source_row_id',
            'CHECKNUM': 'check_no',
        })
        # Convert date format like 20250102120000[0:8]
        if 'txn_date' in df.columns:
            df['txn_date'] = pd.to_datetime(df['txn_date'].astype(str).str.slice(0,8), errors='coerce', format='%Y%m%d')
        df['pay_type'] = 'bank_txn'
        return df[['txn_date', 'amount', 'memo', 'source_row_id', 'check_no', 'pay_type']]
    except Exception:
        # Minimal XML parse
        import xml.etree.ElementTree as ET
        tree = ET.parse(path)
        root = tree.getroot()
        rows = []
        for trn in root.iter('STMTTRN'):
            dt = trn.findtext('DTPOSTED')
            amt = trn.findtext('TRNAMT')
            memo = trn.findtext('NAME') or trn.findtext('MEMO')
            fitid = trn.findtext('FITID')
            chk = trn.findtext('CHECKNUM')
            d = None
            if dt:
                d = pd.to_datetime(dt[:8], errors='coerce', format='%Y%m%d')
            rows.append({'txn_date': d, 'amount': float(amt) if amt else None, 'memo': memo, 'source_row_id': fitid, 'check_no': chk, 'pay_type': 'bank_txn'})
        return pd.DataFrame(rows)


def parse_spreadsheet(path: Path) -> pd.DataFrame:
    # Read Excel/CSV then attempt to find driver pay columns heuristically
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path, sheet_name=None)
        # Combine all sheets with a sheet indicator
        parts = []
        for sheet, sdf in df.items():
            sdf = sdf.copy()
            sdf['source_sheet'] = sheet
            parts.append(sdf)
        df = pd.concat(parts, ignore_index=True)

    # Standardize column names
    df.columns = [str(c).strip().lower().replace('\n', ' ').replace('  ', ' ') for c in df.columns]

    # Heuristic mappings
    possible_date = [c for c in df.columns if 'date' in c or 'txn' in c or 'cheque date' in c or 'pay date' in c]
    possible_driver = [c for c in df.columns if 'driver' in c or 'employee' in c or 'name' in c]
    possible_amount = [c for c in df.columns if any(k in c for k in ['amount','gross','net','total','wage','pay','cheque','check amount'])]
    memo_cols = [c for c in df.columns if 'memo' in c or 'desc' in c or 'description' in c or 'note' in c]
    check_cols = [c for c in df.columns if 'cheque' in c or 'check #' in c or 'check no' in c or 'cheque #' in c]

    out = pd.DataFrame()
    out['txn_date'] = pd.to_datetime(df[possible_date[0]], errors='coerce') if possible_date else pd.NaT
    out['driver_name'] = df[possible_driver[0]] if possible_driver else None
    # Pick amount column preference: gross > net > amount > total
    amt_col = None
    for k in ['gross','net','amount','total','pay']:
        for c in possible_amount:
            if k in c:
                amt_col = c
                break
        if amt_col:
            break
    if amt_col is None and possible_amount:
        amt_col = possible_amount[0]
    out['amount'] = pd.to_numeric(df[amt_col], errors='coerce') if amt_col else None
    out['memo'] = df[memo_cols[0]] if memo_cols else None
    out['check_no'] = df[check_cols[0]] if check_cols else None
    out['source_row_id'] = df.index.astype(str)
    out['pay_type'] = 'sheet'
    if 'source_sheet' in df.columns:
        out['source_sheet'] = df['source_sheet']
    return out


def insert_rows(conn, file_id: int, df: pd.DataFrame, source_file: str):
    df = df.copy()
    df['source_file'] = source_file
    df['driver_id'] = None
    df['gross_amount'] = None
    df['expense_amount'] = None
    df['net_amount'] = None

    # Normalize types
    if 'txn_date' in df.columns:
        df['txn_date'] = pd.to_datetime(df['txn_date'], errors='coerce')
    if 'amount' in df.columns:
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

    cols = ['file_id','source_row_id','source_line_no','txn_date','driver_name','driver_id','pay_type','gross_amount','expense_amount','net_amount','amount','currency','memo','check_no','account','category','vendor','source_sheet','source_file']
    df['file_id'] = file_id
    if 'source_line_no' not in df.columns:
        df['source_line_no'] = pd.RangeIndex(start=1, stop=len(df)+1, step=1)
    for c in cols:
        if c not in df.columns:
            df[c] = None

    # Drop completely empty rows
    df = df[(df['txn_date'].notna()) | (df['amount'].notna()) | (df['driver_name'].notna())]

    tuples = [tuple(df[c] for c in cols) for _, df in df[cols].iterrows()]

    cur = conn.cursor()
    cur.executemany(
        """
        INSERT INTO public.staging_driver_pay (
            file_id, source_row_id, source_line_no, txn_date, driver_name, driver_id, pay_type,
            gross_amount, expense_amount, net_amount, amount, currency, memo, check_no, account, category, vendor, source_sheet, source_file
        ) VALUES (
            %(file_id)s, %(source_row_id)s, %(source_line_no)s, %(txn_date)s, %(driver_name)s, %(driver_id)s, %(pay_type)s,
            %(gross_amount)s, %(expense_amount)s, %(net_amount)s, %(amount)s, %(currency)s, %(memo)s, %(check_no)s, %(account)s, %(category)s, %(vendor)s, %(source_sheet)s, %(source_file)s
        ) ON CONFLICT DO NOTHING
        """,
        [dict(zip(cols, row)) for row in tuples]
    )
    conn.commit()
    cur.close()
    return len(tuples)


def process_file(conn, path: Path) -> None:
    fr = FileRecord(
        file_path=str(path),
        file_name=path.name,
        file_type=path.suffix.lower().lstrip('.'),
        source_hash=sha256_file(path)
    )
    file_id = upsert_file(conn, fr)
    try:
        if path.suffix.lower() == '.qbo':
            df = parse_qbo(path)
        elif path.suffix.lower() in {'.csv', '.xlsx', '.xls'}:
            df = parse_spreadsheet(path)
        else:
            mark_file_status(conn, file_id, 'error', 0, f'Unsupported type: {path.suffix}')
            return
        rows = insert_rows(conn, file_id, df, source_file=path.name)
        first_date = pd.to_datetime(df['txn_date'], errors='coerce').min()
        last_date = pd.to_datetime(df['txn_date'], errors='coerce').max()
        mark_file_status(conn, file_id, 'parsed', rows=rows, dates=(first_date, last_date))
    except Exception as e:
        mark_file_status(conn, file_id, 'error', 0, err=str(e))
        raise


def discover_files() -> Iterable[Path]:
    for base in QB_DIRS:
        p = Path(base)
        if not p.exists():
            continue
        for path in p.rglob('*'):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXT:
                yield path


def main():
    conn = connect_db()
    ensure_migration_ran(conn)
    for path in discover_files():
        print(f"Processing {path}...")
        process_file(conn, path)
    conn.close()

if __name__ == '__main__':
    main()
