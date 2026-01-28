import os
import re
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd
import pdfplumber
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

QB_DIRS = [
    r"L:\\limo\\quickbooks",
    r"L:\\limo\\quickbooks\\New folder",
]

SUPPORTED_EXT = {'.csv', '.xlsx', '.xls', '.qbo', '.pdf'}

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
    cur.execute(
        """
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
            created_at TIMESTAMPTZ DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_sdp_txn_date ON public.staging_driver_pay(txn_date);
        CREATE INDEX IF NOT EXISTS idx_sdp_driver_name ON public.staging_driver_pay(driver_name);
        CREATE INDEX IF NOT EXISTS idx_sdp_file_id ON public.staging_driver_pay(file_id);
        """
    )
    # Expression-based uniqueness via unique index
    cur.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = 'ux_staging_driver_pay_dedup' AND n.nspname = 'public'
            ) THEN
                CREATE UNIQUE INDEX ux_staging_driver_pay_dedup
                ON public.staging_driver_pay (
                    file_id,
                    coalesce(source_row_id, ''),
                    coalesce(source_line_no, 0),
                    coalesce(txn_date, DATE '1900-01-01'),
                    coalesce(amount, 0),
                    coalesce(memo, '')
                );
            END IF;
        END$$;
        """
    )
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


def mark_file_status(conn, file_id: int, status: str, rows: int = 0, err: Optional[str] = None, dates: Optional[Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]] = None):
    cur = conn.cursor()
    first_date = dates[0].date() if dates and pd.notna(dates[0]) else None
    last_date = dates[1].date() if dates and pd.notna(dates[1]) else None
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
    try:
        df = pd.read_xml(path, xpath='//STMTTRN')
        df = df.rename(columns={
            'DTPOSTED': 'txn_date',
            'TRNAMT': 'amount',
            'NAME': 'memo',
            'FITID': 'source_row_id',
            'CHECKNUM': 'check_no',
        })
        if 'txn_date' in df.columns:
            df['txn_date'] = pd.to_datetime(df['txn_date'].astype(str).str.slice(0,8), errors='coerce', format='%Y%m%d')
        df['pay_type'] = 'bank_txn'
        return df[['txn_date', 'amount', 'memo', 'source_row_id', 'check_no', 'pay_type']]
    except Exception:
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
                d = pd.to_datetime(str(dt)[:8], errors='coerce', format='%Y%m%d')
            rows.append({'txn_date': d, 'amount': float(amt) if amt else None, 'memo': memo, 'source_row_id': fitid, 'check_no': chk, 'pay_type': 'bank_txn'})
        return pd.DataFrame(rows)


def parse_spreadsheet(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == '.csv':
        df = pd.read_csv(path)
    else:
        excel = pd.read_excel(path, sheet_name=None)
        parts = []
        for sheet, sdf in excel.items():
            sdf = sdf.copy()
            sdf['source_sheet'] = sheet
            parts.append(sdf)
        df = pd.concat(parts, ignore_index=True)

    df.columns = [str(c).strip().lower().replace('\n', ' ') for c in df.columns]

    possible_date = [c for c in df.columns if any(k in c for k in ['date','txn','cheque date','pay date'])]
    possible_driver = [c for c in df.columns if any(k in c for k in ['driver','employee','name'])]
    possible_amount = [c for c in df.columns if any(k in c for k in ['amount','gross','net','total','wage','pay','cheque','check amount'])]
    memo_cols = [c for c in df.columns if any(k in c for k in ['memo','desc','description','note'])]
    check_cols = [c for c in df.columns if 'check' in c or 'cheque' in c]

    out = pd.DataFrame()
    out['txn_date'] = pd.to_datetime(df[possible_date[0]], errors='coerce') if possible_date else pd.NaT
    out['driver_name'] = df[possible_driver[0]] if possible_driver else None

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


def parse_pdf(path: Path) -> pd.DataFrame:
    rows = []
    date_pattern = re.compile(r'(\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b\d{2}[-/]\d{2}[-/]\d{4}\b)')
    amt_pattern = re.compile(r'(\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)')
    name_pattern = re.compile(r'([A-Z][a-z]+,?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)')
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                for line_no, line in enumerate(text.splitlines(), start=1):
                    amt_m = amt_pattern.search(line)
                    name_m = name_pattern.search(line)
                    if amt_m and name_m:
                        amt = amt_m.group(1).replace('$','').replace(',','')
                        try:
                            amt_val = float(amt)
                        except Exception:
                            continue
                        date_m = date_pattern.search(line)
                        d = None
                        if date_m:
                            d = pd.to_datetime(date_m.group(1), errors='coerce', dayfirst=False, infer_datetime_format=True)
                        rows.append({
                            'txn_date': d,
                            'driver_name': name_m.group(1),
                            'amount': amt_val,
                            'memo': line.strip(),
                            'source_row_id': f'line-{line_no}',
                            'source_line_no': line_no,
                            'pay_type': 'pdf'
                        })
    except Exception as e:
        # Return empty frame on malformed PDFs; caller will mark file error
        return pd.DataFrame()
    return pd.DataFrame(rows)


def insert_rows(conn, file_id: int, df: pd.DataFrame, source_file: str) -> int:
    df = df.copy()
    df['source_file'] = source_file
    for c in ['driver_id','gross_amount','expense_amount','net_amount','currency','account','category','vendor','source_sheet','check_no','memo','driver_name','amount','txn_date','source_row_id']:
        if c not in df.columns:
            df[c] = None
    df['currency'] = df['currency'].fillna('CAD')

    df['txn_date'] = pd.to_datetime(df['txn_date'], errors='coerce')
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')

    df['file_id'] = file_id
    if 'source_line_no' not in df.columns:
        df['source_line_no'] = pd.RangeIndex(start=1, stop=len(df)+1, step=1)

    cols = ['file_id','source_row_id','source_line_no','txn_date','driver_name','driver_id','pay_type','gross_amount','expense_amount','net_amount','amount','currency','memo','check_no','account','category','vendor','source_sheet','source_file']

    # Drop rows that are entirely empty
    df = df[(df['txn_date'].notna()) | (df['amount'].notna()) | (df['driver_name'].notna())]

    records = [dict(zip(cols, row)) for row in df[cols].itertuples(index=False, name=None)]

    if not records:
        return 0

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
        records,
    )
    conn.commit()
    cur.close()
    return len(records)


def process_file(conn, path: Path) -> None:
    fr = FileRecord(
        file_path=str(path),
        file_name=path.name,
        file_type=path.suffix.lower().lstrip('.'),
        source_hash=sha256_file(path)
    )
    file_id = upsert_file(conn, fr)
    try:
        ext = path.suffix.lower()
        if ext == '.qbo':
            df = parse_qbo(path)
        elif ext in {'.csv', '.xlsx', '.xls'}:
            df = parse_spreadsheet(path)
        elif ext == '.pdf':
            df = parse_pdf(path)
        else:
            mark_file_status(conn, file_id, 'error', 0, f'Unsupported type: {ext}')
            return
        rows = insert_rows(conn, file_id, df, source_file=path.name)
        first_date = pd.to_datetime(df['txn_date'], errors='coerce').min() if 'txn_date' in df.columns else pd.NaT
        last_date = pd.to_datetime(df['txn_date'], errors='coerce').max() if 'txn_date' in df.columns else pd.NaT
        status = 'parsed' if rows > 0 else 'parsed-empty'
        mark_file_status(conn, file_id, status, rows=rows, dates=(first_date, last_date))
    except Exception as e:
        mark_file_status(conn, file_id, 'error', 0, err=str(e))
        print(f"Error processing {path}: {e}")


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
