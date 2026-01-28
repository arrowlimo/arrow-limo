"""
Import 2013 receipts from the Excel exports into receipts table.
- Targets files:
  * L:\\limo\\qbb\\backups\\oldalms\\docs\\email attacmetns accounitn\\2013 Revenue & Receipts queries.xlsx
  * L:\\limo\\qbb\\backups\\oldalms\\docs\\email attacmetns accounitn\\2013 Revenue & Receipts queries1.xlsx
- Flexible column mapping (date, vendor, description, amount, gst)
- GST included logic (AB 5% by default) when only gross is present
- Idempotent via source_hash (date|vendor|gross|desc)
"""
import os
import sys
import hashlib
import pandas as pd
import psycopg2
from datetime import datetime

FILES = [
    r"L:\\limo\\qbb\\backups\\oldalms\\docs\\email attacmetns accounitn\\2013 Revenue & Receipts queries.xlsx",
    r"L:\\limo\\qbb\\backups\\oldalms\\docs\\email attacmetns accounitn\\2013 Revenue & Receipts queries1.xlsx",
]

DB = {
    'host': os.getenv('DB_HOST','localhost'),
    'dbname': os.getenv('DB_NAME','almsdata'),
    'user': os.getenv('DB_USER','postgres'),
    'password': os.getenv('DB_PASSWORD','***REMOVED***'),
}

TAX_RATE_AB = 0.05


def calculate_gst_included(total: float, rate: float=TAX_RATE_AB):
    if total is None:
        return 0.0, 0.0
    gst = round(total * rate / (1+rate), 2)
    net = round(total - gst, 2)
    return gst, net


def load_any_sheet(path: str) -> pd.DataFrame:
    # Try default first sheet
    try:
        df = pd.read_excel(path)
        # Standardize header: lower, strip, underscores
        df.columns = (
            df.columns.astype(str)
              .str.strip()
              .str.lower()
              .str.replace(' ', '_')
              .str.replace('-', '_')
        )
        return df
    except Exception:
        pass
    # Fallback: read without header and attempt detection
    df = pd.read_excel(path, header=None)
    # Promote a likely header row if found (row containing words like Date/Amount/Vendor)
    header_idx = None
    for i in range(min(10, len(df))):
        row_vals = [str(x).strip().lower() for x in df.iloc[i].tolist()]
        if any('date' in v for v in row_vals) and (any('amount' in v for v in row_vals) or any('total' in v for v in row_vals)):
            header_idx = i
            break
    if header_idx is not None:
        df.columns = (
            df.iloc[header_idx]
              .astype(str)
              .str.strip()
              .str.lower()
              .str.replace(' ', '_')
              .str.replace('-', '_')
        )
        df = df.iloc[header_idx+1:].reset_index(drop=True)
    else:
        # Generic column names
        df.columns = [f'c{i}' for i in range(df.shape[1])]
    return df


DATE_CANDIDATES = ['date','txn_date','receipt_date','transaction_date','payment_date']
VENDOR_CANDIDATES = ['vendor','name','payee','customer','supplier']
DESC_CANDIDATES = ['description','memo','details','note','notes']
GROSS_CANDIDATES = ['gross_amount','amount','total','total_amount']
GST_CANDIDATES = ['gst','hst','tax','sales_tax']


def pick_col(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    # try fuzzy contains
    for col in df.columns:
        if any(c in col for c in candidates):
            return col
    return None


def get_existing_hashes(cur):
    cur.execute("""
        SELECT source_hash FROM receipts
    """)
    return {r[0] for r in cur.fetchall() if r[0]}


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import 2013 receipts from Excel')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    frames = []
    failed = []
    for f in FILES:
        if not os.path.exists(f):
            failed.append((f,'not found'))
            continue
        try:
            df = load_any_sheet(f)
            df['__source_file'] = f
            frames.append(df)
            print(f"Loaded {len(df)} rows from {f}")
        except Exception as e:
            failed.append((f, str(e)))
            print(f"[WARN]  Failed to read {f}: {e}")

    if not frames:
        print('[FAIL] No readable Excel files for 2013 receipts')
        if failed:
            print('\nFailed files:')
            for p,e in failed:
                print(f'  - {p}: {e}')
        sys.exit(1)

    df = pd.concat(frames, ignore_index=True)

    date_col = pick_col(df, DATE_CANDIDATES)
    vendor_col = pick_col(df, VENDOR_CANDIDATES)
    desc_col = pick_col(df, DESC_CANDIDATES)
    gross_col = pick_col(df, GROSS_CANDIDATES)
    gst_col = pick_col(df, GST_CANDIDATES)

    if not date_col or not gross_col:
        # Try heuristic detection by scanning columns for datelike and numeric
        date_col = None
        gross_col = None
        for col in df.columns:
            # date-like if many parseable dates
            try:
                dt = pd.to_datetime(df[col], errors='coerce')
                if dt.notna().sum() >= max(5, int(0.2*len(df))):
                    date_col = col
                    break
            except Exception:
                continue
        # Pick numeric column with many non-zero values
        numeric_candidates = []
        for col in df.columns:
            try:
                vals = pd.to_numeric(df[col], errors='coerce')
                if vals.notna().sum() >= max(5, int(0.2*len(df))):
                    numeric_candidates.append((col, (vals.abs()>0).sum()))
            except Exception:
                continue
        if numeric_candidates:
            numeric_candidates.sort(key=lambda x: x[1], reverse=True)
            gross_col = numeric_candidates[0][0]
        if not date_col or not gross_col:
            print(f"[FAIL] Required columns missing. date_col={date_col}, gross_col={gross_col}")
            sys.exit(1)

    out = pd.DataFrame()
    out['receipt_date'] = pd.to_datetime(df[date_col], errors='coerce').dt.date
    out = out[out['receipt_date'].notna()].copy()
    out['vendor_name'] = df[vendor_col].astype(str) if vendor_col else 'Unknown'
    out['description'] = df[desc_col].astype(str) if desc_col else ''
    gross = pd.to_numeric(df[gross_col], errors='coerce').fillna(0.0)
    out['gross_amount'] = gross

    if gst_col and gst_col in df.columns:
        gst_val = pd.to_numeric(df[gst_col], errors='coerce').fillna(0.0)
        out['gst_amount'] = gst_val.round(2)
        out['net_amount'] = (out['gross_amount'] - out['gst_amount']).round(2)
    else:
        gst, net = [], []
        for val in out['gross_amount']:
            g, n = calculate_gst_included(val)
            gst.append(g); net.append(n)
        out['gst_amount'] = gst
        out['net_amount'] = net

    # Additional fields
    out['source_system'] = 'QuickBooks-Excel-2013'
    out['currency'] = 'C'
    out['created_from_banking'] = False
    
    # Build source_hash
    def mk_hash(r):
        s = f"{r['receipt_date']}|{r['vendor_name']}|{r['gross_amount']}|{r['description']}"
        return hashlib.sha256(s.encode()).hexdigest()
    out['source_hash'] = out.apply(mk_hash, axis=1)

    # Connect and dedupe by source_hash
    conn = psycopg2.connect(**DB)
    try:
        cur = conn.cursor()
        existing = get_existing_hashes(cur)
        pre = len(out)
        to_write = out[~out['source_hash'].isin(existing)].copy()
        print(f"Prepared {pre} receipts; existing by hash: {pre-len(to_write)}; to insert: {len(to_write)}")

        if args.dry_run:
            print('\n[OK] DRY RUN: no changes written')
            if failed:
                print('\nFailed files:')
                for p,e in failed:
                    print(f'  - {p}: {e}')
            return

        inserted = 0
        for _, r in to_write.iterrows():
            cur.execute(
                """
                INSERT INTO receipts (source_system, source_reference, receipt_date, vendor_name, description, currency, gross_amount, gst_amount, created_from_banking, source_hash, source_file)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source_hash) DO NOTHING
                """,
                (
                    r['source_system'], None, r['receipt_date'], r['vendor_name'], r['description'], r['currency'],
                    float(r['gross_amount']), float(r['gst_amount']), bool(r['created_from_banking']), r['source_hash'], df.loc[r.name, '__source_file'] if '__source_file' in df.columns else None
                )
            )
            if cur.rowcount>0:
                inserted += 1
        conn.commit()
        print(f"\n[OK] Inserted {inserted} receipts for 2013")
        if failed:
            print('\nFailed files (skipped):')
            for p,e in failed:
                print(f'  - {p}: {e}')
    finally:
        try:
            conn.close()
        except:
            pass


if __name__ == '__main__':
    main()
