#!/usr/bin/env python3
"""
Watch L:\\limo\\bulk_upload (or a custom folder) for new receipts CSV files and ingest them.
- Supports CSV with columns like: receipt_date/Date issued, vendor_name/Vendor, gross_amount/Total, gst/gst_amount/Tax
- Upserts into receipts by composite key (date + vendor + amount) or inserts if missing
- Moves processed files to bulk_upload\\archive with a timestamp suffix
- Records ingest results in receipts_ingest_log

Usage:
- One-shot scan (default): python scripts/watch_bulk_receipts_upload.py
- Continuous watch:       python scripts/watch_bulk_receipts_upload.py --watch --interval 10
- Custom folder:          python scripts/watch_bulk_receipts_upload.py --dir "L:\\path\\to\\folder"

You can also set BULK_UPLOAD_DIR env var to override the default bulk folder.
"""
import os
import time
import csv
import shutil
from datetime import datetime, timedelta
import argparse
import hashlib
import psycopg2
import hashlib
import re

# Defaults can be overridden via --dir or BULK_UPLOAD_DIR env var
DEFAULT_BULK_DIR = os.environ.get('BULK_UPLOAD_DIR', r"L:\\limo\\bulk_upload")

# Will be set in main() to respect CLI/env overrides
BULK_DIR = DEFAULT_BULK_DIR
ARCHIVE_DIR = None

DB = dict(
    dbname=os.environ.get('DB_NAME', 'almsdata'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', '***REDACTED***'),
    host=os.environ.get('DB_HOST', 'localhost'),
    port=int(os.environ.get('DB_PORT', '5432')),
)

# Cache of receipts columns and whether they are generated (read-only) to avoid invalid writes
RECEIPTS_COL_INFO: dict[str, dict] = {}

# --- CSV shape detection helpers -------------------------------------------
def _read_header(path: str):
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            # If header is None or empty, return empty list
            return [h.strip() for h in (header or [])]
    except Exception:
        return []

def is_probably_receipts_csv(path: str) -> bool:
    """Heuristic: receipts CSVs have at least 2 of (date, vendor, amount) headers under common names."""
    headers = set(h.lower() for h in _read_header(path))
    if not headers:
        return False
    date_keys = { 'date issued', 'receipt_date', 'date' }
    vendor_keys = { 'vendor', 'vendor name', 'vendor_name' }
    amount_keys = { 'total', 'gross_amount', 'amount' }
    hits = 0
    if headers & date_keys: hits += 1
    if headers & vendor_keys: hits += 1
    if headers & amount_keys: hits += 1
    return hits >= 2

def is_probably_banking_csv(path: str) -> bool:
    """Heuristic: banking CSVs often include transaction date/description and debit/credit columns."""
    headers = set(h.lower() for h in _read_header(path))
    if not headers:
        return False
    has_date = any(k in headers for k in ('trans_date','transaction date','date'))
    has_desc = any(k in headers for k in ('trans_description','transaction description','description','description 1'))
    has_debit_credit = ('debit' in headers) and ('credit' in headers)
    has_account_number = any(k in headers for k in ('account number','account_number','acct','acct number'))
    # Banking if date+desc+(debit&credit) OR presence of account number with debit/credit
    return (has_date and has_desc and has_debit_credit) or (has_debit_credit and has_account_number)

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def is_file_ready(path: str, stable_seconds: int = 3) -> bool:
    """Return True if the file appears stable (size and mtime unchanged for a short period).
    This helps avoid processing a file that's still being copied into the folder.
    """
    try:
        size1 = os.path.getsize(path)
        mtime1 = os.path.getmtime(path)
    except FileNotFoundError:
        return False
    # If very fresh, give it a moment first
    if (time.time() - mtime1) < stable_seconds:
        return False
    time.sleep(1)
    try:
        size2 = os.path.getsize(path)
        mtime2 = os.path.getmtime(path)
    except FileNotFoundError:
        return False
    return size1 == size2 and mtime1 == mtime2

def ensure_ingest_log(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS receipts_ingest_log (
          id SERIAL PRIMARY KEY,
          file_name text NOT NULL,
          file_hash text NOT NULL,
          started_at timestamp DEFAULT now(),
          finished_at timestamp,
          status text,
          rows_inserted int DEFAULT 0,
          rows_updated int DEFAULT 0,
          error text
        );
        CREATE INDEX IF NOT EXISTS idx_receipts_ingest_log_hash ON receipts_ingest_log(file_hash);
        """
    )

def ensure_receipts_columns(cur):
        """Ensure receipts table has enhanced columns used by ingestion.
        Columns: net_amount, gst_code, fuel_amount, vehicle_id, split_key, split_group_total, source_file
        """
        cur.execute(
                """
                DO $$ BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='receipts' AND column_name='net_amount'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN net_amount numeric(12,2);
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='receipts' AND column_name='gst_code'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN gst_code text;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='receipts' AND column_name='fuel_amount'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN fuel_amount numeric(12,2);
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='receipts' AND column_name='vehicle_id'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN vehicle_id text;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='receipts' AND column_name='split_key'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN split_key text;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='receipts' AND column_name='split_group_total'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN split_group_total numeric(12,2);
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='receipts' AND column_name='source_file'
                    ) THEN
                        ALTER TABLE receipts ADD COLUMN source_file text;
                    END IF;
                END $$;
                """
        )

def parse_bool(val):
    return str(val).strip().lower() in {"yes","true","1"}

def parse_float(val):
    try:
        s = str(val).replace('$','').replace(',','').strip()
        return float(s) if s else None
    except Exception:
        return None

def parse_date(val):
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%m/%d/%Y %I:%M %p', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None

def normalize_row(row: dict):
    # Map common headers to our receipt fields (Epson + manual formats)
    date_issued = row.get('Date issued') or row.get('receipt_date') or row.get('Date')
    vendor = row.get('Vendor') or row.get('vendor_name') or row.get('Vendor Name')
    total = row.get('Total') or row.get('gross_amount') or row.get('Amount') or row.get('expense')
    gst = row.get('Tax') or row.get('gst_amount') or row.get('GST')
    desc = row.get('Description') or row.get('description') or row.get('Comment') or row.get('comment')
    
    # Additional Epson receipt manager fields
    payment_method = row.get('Payment Method') or row.get('pay_method') or row.get('Payment')
    category = row.get('Category') or row.get('category') or row.get('expense_account')
    business_personal = row.get('Business/Personal') or row.get('business_personal')
    deductible = row.get('Deductible') or row.get('deductible_status')

    rec = dict(
        receipt_date=parse_date(date_issued),
        vendor_name=(vendor or '').strip() or None,
        gross_amount=parse_float(total),
        gst_amount=parse_float(gst),
        description=(desc or '').strip() or None,
        payment_method=payment_method,
        category=category,
        business_personal=business_personal,
        deductible_status=deductible
    )

    # GST auto-calc if missing/zero and not exempt
    exempt_codes = {'Z', 'EXCL', 'EXEMPT', 'NO GST', 'GST EXEMPT', 'GST EXCL'}
    gst_code_raw = (row.get('GST Code') or row.get('gst_code') or '').strip().upper()
    is_exempt = gst_code_raw in exempt_codes or (rec.get('description') or '').upper().find('EXEMPT') != -1
    if (rec['gross_amount'] is not None
        and (rec['gst_amount'] is None or rec['gst_amount'] == 0)
        and not is_exempt):
        # Treat 'Total' (gross_amount) as tax-included; extract GST portion at 5% of net
        # GST portion = gross * (rate / (1 + rate))
        rate = 0.05
        rec['gst_amount'] = round(rec['gross_amount'] * (rate / (1.0 + rate)), 2)

    # Set GST code: preserve provided code if present; otherwise derive
    if gst_code_raw:
        rec['gst_code'] = gst_code_raw
    else:
        if rec.get('gst_amount') is not None and rec['gst_amount'] > 0:
            rec['gst_code'] = 'G'
        else:
            rec['gst_code'] = 'Z'

    return rec

def load_receipts_col_info(cur):
    global RECEIPTS_COL_INFO
    RECEIPTS_COL_INFO = {}
    cur.execute(
        """
        SELECT column_name, is_generated
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'receipts'
        """
    )
    for name, is_gen in cur.fetchall():
        RECEIPTS_COL_INFO[name] = {
            'is_generated': (str(is_gen).upper() == 'ALWAYS')
        }

def _col_writable(col: str) -> bool:
    info = RECEIPTS_COL_INFO.get(col)
    if not info:
        return False
    return not info.get('is_generated', False)

def extract_vehicle_and_fuel(description: str, vendor: str, gross_amount: float, comment: str = None) -> tuple[str|None, float|None]:
    """Extract vehicle id and fuel amount from description/vendor/comment when marked as fuel.
    - Vehicle ID: search for patterns like 'L-10', 'L-6', card numbers like 3265, 1941
    - Fuel amount: liters from comment field (104.272, 101.115, 8.271) or currency amounts
    """
    text = f"{vendor or ''} {description or ''} {comment or ''}".upper()
    # Check if fuel-like
    if not any(x in text for x in ('FUEL', 'GAS', 'DIESEL', 'PETRO', 'SHELL', 'ESSO', 'CHEVRON', 'CO-OP', 'COOP', 'FUEL_EXPENSE')):
        return None, None

    vehicle_id = None
    # Enhanced vehicle patterns for your data format
    veh_patterns = [
        r"L-([0-9]{1,3})",  # L-10, L-6 format from your examples
        r"VEH[#\s-]*([A-Z0-9-]{2,10})",
        r"UNIT[#\s-]*([A-Z0-9-]{1,10})",
        r"TRK[#\s-]*([A-Z0-9-]{1,10})",
        r"VEHICLE[#\s-]*([A-Z0-9-]{1,10})",
        r"([0-9]{4})",  # 4-digit numbers like 3265, 1941, 8547
    ]
    for pat in veh_patterns:
        m = re.search(pat, text)
        if m:
            vehicle_id = m.group(1)
            break

    # Fuel amount from comment field (liters or currency)
    fuel_amount = None
    # Look for liter amounts like "104.272", "101.115", "8.271"
    liter_match = re.search(r"([0-9]{1,3}\.[0-9]{1,3})", comment or "")
    if liter_match:
        fuel_amount = float(liter_match.group(1))
    else:
        # Fallback to currency amounts in description
        nums = re.findall(r"\$?\s*([0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)", text)
        candidates = []
        for n in nums:
            try:
                val = float(n.replace(',', ''))
                if gross_amount is None or val <= (gross_amount + 0.01):
                    candidates.append(val)
            except Exception:
                continue
        if candidates:
            fuel_amount = max(candidates)  # Take largest reasonable amount

    return vehicle_id, (round(fuel_amount, 2) if fuel_amount is not None else None)

def parse_split_key(description: str, vendor: str) -> str|None:
    """Detect split group key hints from description.
    Examples it will catch: 'split 1/2', 'split: ABC123', 'split group XYZ'
    Returns a normalized split key string or None.
    """
    text = f"{vendor or ''} {description or ''}".upper()
    if 'SPLIT' not in text and 'SPLT' not in text:
        return None
    # Identifier after 'SPLIT' or 'SPLT'
    m = re.search(r"SPLI?T[:#\s-]*([A-Z0-9_-]{2,20})", text)
    if m:
        return f"SPLIT:{m.group(1)}"
    # Fraction pattern like 1/2, 2/3
    m2 = re.search(r"([0-9]{1,2})\s*/\s*([0-9]{1,2})", text)
    if m2:
        return f"SPLIT:{m2.group(1)}/{m2.group(2)}:{hash((vendor or '').lower()) & 0xffff}"
    # Otherwise group by vendor-based generic split marker
    return f"SPLIT:{(vendor or '').strip().upper()}"

def make_source_hash(r: dict, file_hash: str, line_no: int) -> str:
    """Deterministic hash to enforce idempotency and satisfy unique(source_hash)."""
    parts = [
        str(r.get('receipt_date') or ''),
        (r.get('vendor_name') or '').lower(),
        f"{(r.get('gross_amount') if r.get('gross_amount') is not None else '')}",
        (r.get('description') or '').strip().lower(),
        file_hash,
        str(line_no),
    ]
    data = "|".join(parts)
    return hashlib.md5(data.encode('utf-8')).hexdigest()

def upsert_receipt(cur, r: dict, source_hash: str) -> tuple[int,int]:
    """Upsert on unique source_hash; also attempt a prior composite update to enrich existing rows."""
    if not (r['receipt_date'] and r['vendor_name'] and r['gross_amount'] is not None):
        return (0,0)
    # Best-effort composite update for rows that predate hashing (only writable columns)
    update_sets = []
    update_params = []
    def add_update(col, val):
        if _col_writable(col):
            update_sets.append(f"{col} = COALESCE(%s, {col})")
            update_params.append(val)

    add_update('gst_amount', r.get('gst_amount'))
    add_update('description', r.get('description'))
    add_update('net_amount', r.get('net_amount'))
    add_update('gst_code', r.get('gst_code'))
    add_update('fuel_amount', r.get('fuel_amount'))
    add_update('fuel', r.get('fuel'))  # Legacy fuel column
    add_update('vehicle_id', r.get('vehicle_id'))
    add_update('split_key', r.get('split_key'))
    add_update('split_group_total', r.get('split_group_total'))
    add_update('source_file', r.get('source_file'))
    add_update('payment_method', r.get('payment_method'))
    add_update('category', r.get('category'))
    add_update('expense_account', r.get('expense_account'))
    add_update('business_personal', r.get('business_personal'))
    add_update('deductible_status', r.get('deductible_status'))

    if update_sets:
        sql = (
            "UPDATE receipts SET " + ", ".join(update_sets) +
            " WHERE vendor_name = %s AND gross_amount = %s AND receipt_date = %s RETURNING id"
        )
        cur.execute(sql, tuple(update_params + [r['vendor_name'], r['gross_amount'], r['receipt_date']]))
    else:
        cur.execute("SELECT 0 WHERE FALSE")  # set rowcount = 0 safely
    if cur.rowcount > 0:
        return (0, cur.rowcount)
    # Insert or update on source_hash with only writable/available columns
    insert_cols = ['receipt_date', 'vendor_name', 'gross_amount', 'gst_amount', 'description', 'source_hash']
    optional_cols = ['net_amount', 'gst_code', 'fuel_amount', 'fuel', 'vehicle_id', 'split_key', 'split_group_total', 'source_file', 'payment_method', 'category', 'expense_account', 'business_personal', 'deductible_status']
    for col in optional_cols:
        if _col_writable(col):
            insert_cols.insert(-1, col)  # insert before source_hash
    insert_placeholders = ", ".join(["%s"] * len(insert_cols))
    insert_values = [r.get(c) if c != 'source_hash' else source_hash for c in insert_cols]

    # Build DO UPDATE SET list from writable optional columns
    update_sets2 = []
    for col in ['gst_amount', 'description'] + [c for c in optional_cols if _col_writable(c)]:
        if col in ('receipt_date', 'vendor_name', 'gross_amount', 'source_hash'):
            continue
        if col in RECEIPTS_COL_INFO:  # only if column exists
            update_sets2.append(f"{col} = COALESCE(EXCLUDED.{col}, receipts.{col})")

    if update_sets2:
        sql = (
            f"INSERT INTO receipts ({', '.join(insert_cols)}) VALUES ({insert_placeholders}) "
            + "ON CONFLICT (source_hash) DO UPDATE SET "
            + ", ".join(update_sets2)
            + " RETURNING (xmax = 0) AS inserted"
        )
    else:
        sql = (
            f"INSERT INTO receipts ({', '.join(insert_cols)}) VALUES ({insert_placeholders}) "
            + "ON CONFLICT (source_hash) DO NOTHING "
            + "RETURNING (xmax = 0) AS inserted"
        )
    cur.execute(sql, tuple(insert_values))
    inserted_flag = cur.fetchone()[0]
    if inserted_flag:
        return (1, 0)
    else:
        return (0, 1)

def process_file(path: str, *, archive_after: bool = True):
    file_name = os.path.basename(path)
    file_hash = sha256_file(path)
    conn = psycopg2.connect(**DB)
    rows_ins = rows_upd = 0
    try:
        with conn:
            with conn.cursor() as cur:
                ensure_ingest_log(cur)
                ensure_receipts_columns(cur)
                # Load receipts column metadata (existence, generated columns)
                load_receipts_col_info(cur)
                cur.execute(
                    """
                    INSERT INTO receipts_ingest_log (file_name, file_hash, status)
                    VALUES (%s, %s, 'started')
                    RETURNING id
                    """,
                    (file_name, file_hash)
                )
                log_id = cur.fetchone()[0]

                # Load all rows to compute split totals
                parsed_rows = []
                with open(path, newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for i, row in enumerate(reader, start=2):  # start=2 to account for header
                        r = normalize_row(row)
                        r['source_file'] = file_name
                        
                        # Get comment field for vehicle/fuel parsing
                        comment = row.get('comment') or row.get('Comment') or ''
                        
                        # Enrich with vehicle/fuel if fuel-like (now includes comment parsing)
                        vid, famt = extract_vehicle_and_fuel(r.get('description'), r.get('vendor_name'), r.get('gross_amount'), comment)
                        if vid:
                            r['vehicle_id'] = vid
                        if famt is not None:
                            r['fuel_amount'] = famt
                            r['fuel'] = famt  # Also populate legacy fuel column
                        
                        # Detect split group key from description or split pattern
                        sk = parse_split_key(r.get('description'), r.get('vendor_name'))
                        if sk:
                            r['split_key'] = sk
                        
                        # Map category to expense field for compatibility
                        if r.get('category'):
                            r['expense_account'] = r['category']
                            
                        parsed_rows.append((i, r))

                # Compute split totals per key within this file
                split_totals: dict[str, float] = {}
                for _, r in parsed_rows:
                    sk = r.get('split_key')
                    if sk and r.get('gross_amount') is not None:
                        split_totals[sk] = round(split_totals.get(sk, 0.0) + float(r['gross_amount']), 2)

                # Upsert rows with computed split_group_total
                for i, r in parsed_rows:
                    if r.get('split_key'):
                        r['split_group_total'] = split_totals.get(r['split_key'])
                    sh = make_source_hash(r, file_hash, i)
                    ins, upd = upsert_receipt(cur, r, sh)
                    rows_ins += ins
                    rows_upd += upd

                cur.execute(
                    """
                    UPDATE receipts_ingest_log
                       SET finished_at = now(), status='success',
                           rows_inserted=%s, rows_updated=%s
                     WHERE id=%s
                    """,
                    (rows_ins, rows_upd, log_id)
                )
        # Move file to archive (optional)
        if archive_after:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            dest = os.path.join(ARCHIVE_DIR, f"{ts}__{file_name}")
            shutil.move(path, dest)
            print(f"[OK] Processed {file_name}: inserted={rows_ins}, updated={rows_upd}; archived -> {dest}")
        else:
            print(f"[OK] Processed {file_name}: inserted={rows_ins}, updated={rows_upd}; not archived (per flag)")
    except Exception as e:
        with conn:
            with conn.cursor() as cur:
                ensure_ingest_log(cur)
                cur.execute(
                    """
                    INSERT INTO receipts_ingest_log (file_name, file_hash, status, error)
                    VALUES (%s, %s, 'error', %s)
                    """,
                    (file_name, file_hash, str(e)[:4000])
                )
        print(f"[FAIL] Error processing {file_name}: {e}")
    finally:
        conn.close()

def scan_once():
    # Process any CSV in the bulk folder (non-recursive)
    for name in os.listdir(BULK_DIR):
        path = os.path.join(BULK_DIR, name)
        if not os.path.isfile(path):
            continue
        if not name.lower().endswith('.csv'):
            continue
        if not is_file_ready(path):
            # Skip files that look like they're still being written; will try again on next pass
            continue
        # Only handle receipts-like CSVs here; skip banking and unknown shapes
        if is_probably_banking_csv(path):
            print(f"↪️  Skipping banking CSV in receipts inbox: {name}. Use bank import scripts instead.")
            continue
        if not is_probably_receipts_csv(path):
            print(f"↪️  Skipping unrecognized CSV format: {name}. Expecting receipts columns (Date, Vendor, Total).")
            continue
        process_file(path)

def watch_loop(interval: int = 10):
    print(f"👀 Watching {BULK_DIR} every {interval}s. Press Ctrl+C to stop.")
    try:
        while True:
            scan_once()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("Stopping watch loop.")

def main():
    global BULK_DIR, ARCHIVE_DIR

    parser = argparse.ArgumentParser(description="Ingest receipts CSVs from a bulk folder.")
    parser.add_argument("--dir", dest="bulk_dir", default=DEFAULT_BULK_DIR, help="Folder to watch/scan for CSV files")
    parser.add_argument("--watch", action="store_true", help="Continuously watch the folder with polling")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds for --watch mode")
    parser.add_argument("--file", dest="single_file", help="Process a single CSV file (can be in archive)")
    parser.add_argument("--no-archive", action="store_true", help="Do not archive the file after processing (for --file mode)")
    args = parser.parse_args()

    BULK_DIR = args.bulk_dir
    ARCHIVE_DIR = os.path.join(BULK_DIR, "archive")
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    if args.single_file:
        # Process a single file path, respecting no-archive flag
        process_file(args.single_file, archive_after=not args.no_archive)
    elif args.watch:
        watch_loop(args.interval)
    else:
        # One-shot scan; can be looped externally or scheduled
        scan_once()

if __name__ == '__main__':
    main()
