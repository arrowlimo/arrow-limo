#!/usr/bin/env python3
"""
Enhanced driver pay parser (v6) with GL exclusion and better date extraction.

Key improvements over v5:
1. GL/summary row filtering: exclude rows where driver_name matches non-driver patterns
2. Enhanced date extraction: fallback to filename/path date inference when column date missing
3. Driver code normalization: detect and normalize driver codes (Dr100 -> 100)
4. Better heuristics for driver-level vs summary files

Usage:
  python scripts/ingest_driver_pay_v6.py --dir L:\\limo\\quickbooks --year-filter 2024,2025
"""
import os
import re
import sys
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import pdfplumber
import psycopg2
from psycopg2 import sql

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REDACTED***')

# GL account and summary patterns to exclude
GL_EXCLUSION_PATTERNS = [
    r'\bwages?\b',
    r'\bsalaries\b',
    r'\bcpp\b',
    r'\bei\b',
    r'\bexpense\b',
    r'\bpayable\b',
    r'\breceivable\b',
    r'\bdummy\b',
    r'\bnan\b',
    r'\bsheet\b',
    r'\binput\b',
    r'\bsummary\b',
    r'\btotal\b',
    r'\bsubtotal\b',
    r'\bnet\b',
    r'\bgross\b',
    r'\bequipment\b',
    r'\bsupplies\b',
    r'\btravel\b',
    r'\bsecurity\b',
    r'\bfixed assets\b',
    r'\badvances\b',
    r'\bgratuities\' payable\b',
]
GL_EXCLUSION_RE = re.compile('|'.join(GL_EXCLUSION_PATTERNS), re.IGNORECASE)

# Date extraction from paths
DATE_PATTERNS = [
    (re.compile(r'(\d{4})[-_](\d{2})[-_](\d{2})'), '%Y-%m-%d'),
    (re.compile(r'(\d{4})[-_](\d{2})'), '%Y-%m'),
    (re.compile(r'([A-Z][a-z]{2,8})\s+(\d{4})'), '%B %Y'),
    (re.compile(r'(\d{2})[-_](\d{2})[-_](\d{4})'), '%m-%d-%Y'),
]

def connect_db():
    return psycopg2.connect(dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD)

def ensure_migration_ran(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS public.staging_driver_pay_files (
            id BIGSERIAL PRIMARY KEY,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            source_hash TEXT,
            rows_parsed INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            error_message TEXT,
            first_txn_date DATE,
            last_txn_date DATE,
            processed_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE (file_path)
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
        """
    )

def extract_date_from_path(file_path: str):
    for pat, fmt in DATE_PATTERNS:
        m = pat.search(file_path)
        if m:
            try:
                if fmt == '%Y-%m':
                    return datetime.strptime(f"{m.group(1)}-{m.group(2)}-01", '%Y-%m-%d').date()
                elif fmt == '%B %Y':
                    return datetime.strptime(f"{m.group(1)} {m.group(2)}", '%B %Y').replace(day=1).date()
                else:
                    return datetime.strptime(m.group(0), fmt).date()
            except Exception:
                continue
    return None

def is_driver_name_valid(name: str) -> bool:
    """Return False if name matches GL/summary patterns."""
    if not name or pd.isna(name):
        return False
    s = str(name).strip().lower()
    if not s or s in ('nan', 'none', ''):
        return False
    if GL_EXCLUSION_RE.search(s):
        return False
    # Exclude single-word generic headers
    if len(s.split()) == 1 and s in ('name', 'driver', 'employee', 'total', 'summary'):
        return False
    return True

def normalize_driver_code(name: str) -> str:
    """Normalize driver codes: Dr100 -> 100, DR09 -> 09."""
    s = str(name).strip()
    m = re.match(r'^[Dd][Rr](\d+)$', s)
    if m:
        return m.group(1).lstrip('0') or '0'
    return s

def parse_spreadsheet(path: Path, fallback_date=None) -> pd.DataFrame:
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

    possible_date = [c for c in df.columns if any(k in c for k in ['date','txn','cheque date','pay date','period end'])]
    possible_driver = [c for c in df.columns if any(k in c for k in ['driver','employee','name'])]
    possible_amount = [c for c in df.columns if any(k in c for k in ['amount','gross','net','total','wage','pay','cheque','check amount'])]
    memo_cols = [c for c in df.columns if any(k in c for k in ['memo','desc','description','note'])]
    check_cols = [c for c in df.columns if 'check' in c or 'cheque' in c]

    out = pd.DataFrame()
    out['txn_date'] = pd.to_datetime(df[possible_date[0]], errors='coerce') if possible_date else pd.NaT
    # Fallback to path-inferred date if column date missing
    if out['txn_date'].isna().all() and fallback_date:
        out['txn_date'] = pd.to_datetime(fallback_date)
    
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
    
    # Filter GL/summary rows
    if 'driver_name' in out.columns:
        out = out[out['driver_name'].apply(lambda x: is_driver_name_valid(x))]
    
    return out

def parse_pdf(path: Path, fallback_date=None) -> pd.DataFrame:
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
                        name = name_m.group(1)
                        if not is_driver_name_valid(name):
                            continue
                        date_m = date_pattern.search(line)
                        d = pd.to_datetime(date_m.group(1), errors='coerce') if date_m else (pd.to_datetime(fallback_date) if fallback_date else pd.NaT)
                        rows.append({
                            'txn_date': d,
                            'driver_name': name,
                            'amount': amt_val,
                            'memo': line.strip(),
                            'source_row_id': f'line-{line_no}',
                            'pay_type': 'pdf'
                        })
    except Exception as e:
        print(f"PDF parse error {path}: {e}")
    return pd.DataFrame(rows)

def register_file(cur, path: Path, file_type: str) -> int:
    cur.execute(
        """
        INSERT INTO public.staging_driver_pay_files (file_path, file_name, file_type, source_hash)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (file_path) DO UPDATE SET processed_at = now()
        RETURNING id
        """,
        (str(path), path.name, file_type, 'v6')
    )
    return cur.fetchone()[0]

def insert_rows(cur, file_id: int, df: pd.DataFrame, source_file: str):
    # Normalize driver codes
    if 'driver_name' in df.columns:
        df['driver_name'] = df['driver_name'].apply(lambda x: normalize_driver_code(x) if pd.notna(x) else None)
    
    required = ['driver_id','gross_amount','expense_amount','net_amount','currency','account','category','vendor','source_sheet','check_no','memo','driver_name','amount','txn_date','source_row_id','pay_type']
    for col in required:
        if col not in df.columns:
            df[col] = None
    
    df['file_id'] = file_id
    df['source_file'] = source_file
    
    cols = ['file_id','source_row_id','source_line_no','txn_date','driver_name','driver_id','pay_type','gross_amount','expense_amount','net_amount','amount','currency','memo','check_no','account','category','vendor','source_sheet','source_file']
    df['source_line_no'] = None
    
    for _, row in df.iterrows():
        cur.execute(
            """
            INSERT INTO public.staging_driver_pay (
                file_id, source_row_id, source_line_no, txn_date, driver_name, driver_id, pay_type,
                gross_amount, expense_amount, net_amount, amount, currency, memo, check_no, account, category, vendor, source_sheet, source_file
            )
            VALUES (
                %(file_id)s, %(source_row_id)s, %(source_line_no)s, %(txn_date)s, %(driver_name)s, %(driver_id)s, %(pay_type)s,
                %(gross_amount)s, %(expense_amount)s, %(net_amount)s, %(amount)s, %(currency)s, %(memo)s, %(check_no)s, %(account)s, %(category)s, %(vendor)s, %(source_sheet)s, %(source_file)s
            )
            ON CONFLICT DO NOTHING
            """,
            row.to_dict()
        )

def process_file(cur, path: Path, year_filter=None):
    fallback_date = extract_date_from_path(str(path))
    if year_filter and fallback_date:
        if fallback_date.year not in year_filter:
            return
    
    file_type = path.suffix.lower().replace('.','')
    file_id = register_file(cur, path, file_type)
    
    try:
        if file_type in ('xlsx','xls','csv'):
            df = parse_spreadsheet(path, fallback_date)
        elif file_type == 'pdf':
            df = parse_pdf(path, fallback_date)
        else:
            return
        
        if df.empty:
            return
        
        insert_rows(cur, file_id, df, path.name)
        print(f"[OK] {path.name}: {len(df)} rows")
    except Exception as e:
        print(f"[FAIL] {path.name}: {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default=r'L:\limo\quickbooks', help='Directory to scan')
    ap.add_argument('--year-filter', help='Comma-separated years to process (e.g., 2024,2025)')
    args = ap.parse_args()
    
    year_filter = None
    if args.year_filter:
        year_filter = [int(y.strip()) for y in args.year_filter.split(',')]
    
    conn = connect_db()
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_migration_ran(cur)
                root = Path(args.dir)
                for path in root.rglob('*'):
                    if path.is_file() and path.suffix.lower() in ('.xlsx','.xls','.csv','.pdf'):
                        # Skip excluded files
                        if any(x in path.name.lower() for x in ('journal','ledger','t4','summary report','pd7a','accounts payable')):
                            continue
                        process_file(cur, path, year_filter)
            conn.commit()
    finally:
        conn.close()

if __name__ == '__main__':
    main()
