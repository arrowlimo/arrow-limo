import os
import csv
import hashlib
from datetime import datetime
import psycopg2

# Configuration
CSV_PATH = r"l:\\limo\\mastercard_business_expenses.csv"
BACKUP_PATH = r"l:\\limo\\mastercard_business_expenses.csv.bak"
# Default output is to overwrite the source CSV; if the file is locked (e.g., open in editor),
# we'll fall back to writing a new file alongside it.
OUTPUT_PATH = CSV_PATH
PROVINCE = 'AB'  # for GST included calculation
DEFAULT_CURRENCY = 'CAD'
DEFAULT_STATUS = 'PENDING'
DEFAULT_SOURCE_SYSTEM = 'mastercard_import'


def get_db_connection():
    host = os.environ.get('DB_HOST', 'localhost')
    db = os.environ.get('DB_NAME', 'almsdata')
    user = os.environ.get('DB_USER', 'postgres')
    password = os.environ.get('DB_PASSWORD', '***REMOVED***')
    return psycopg2.connect(host=host, dbname=db, user=user, password=password)


def get_receipts_columns(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'receipts'
            ORDER BY ordinal_position
            """
        )
        return [r[0] for r in cur.fetchall()]


def gst_included_split(gross: float, province: str = 'AB'):
    rates = {
        'AB': 0.05,
        'BC': 0.12,
        'SK': 0.11,
        'MB': 0.12,
        'ON': 0.13,
        'QC': 0.14975,
        'NB': 0.15,
        'NS': 0.15,
        'PE': 0.15,
        'NL': 0.15,
        'YT': 0.05,
        'NT': 0.05,
        'NU': 0.05,
    }
    rate = rates.get(province, 0.05)
    if gross is None:
        return 0.0, 0.0
    gst = round(gross * rate / (1 + rate), 2)
    net = round(gross - gst, 2)
    return gst, net


def normalize_decimal(val):
    if val is None:
        return None
    s = str(val).strip().replace('$', '').replace(',', '')
    if s == '' or s.lower() == 'nan':
        return None
    try:
        return float(s)
    except Exception:
        return None


def build_source_hash(row):
    key = f"{row.get('receipt_date','')}|{row.get('vendor_name','')}|{row.get('gross_amount','')}|{row.get('payment_method','')}|{row.get('description','')}"
    return hashlib.sha256(key.encode('utf-8')).hexdigest()


def main():
    # Connect and fetch receipts columns
    conn = get_db_connection()
    try:
        receipts_cols = get_receipts_columns(conn)
    finally:
        conn.close()

    # Read existing CSV
    with open(CSV_PATH, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        src_rows = list(reader)

    out_rows = []
    for r in src_rows:
        # Map minimal fields if present; else try alternative keys
        receipt_date = r.get('receipt_date') or r.get('date') or r.get('transaction_date')
        vendor_name = r.get('vendor_name') or r.get('merchant') or r.get('merchant_name')
        gross_amount = normalize_decimal(r.get('gross_amount') or r.get('amount') or r.get('total') or r.get('gross'))
        description = r.get('description') or r.get('memo') or r.get('notes') or ''
        category = r.get('category') or ''
        payment_method = r.get('payment_method') or 'Mastercard'
        comment = r.get('comment') or ''
        business_personal = r.get('business_personal') or r.get('business_expense') or ''
        employee_id = r.get('employee_id') or ''

        # Compute GST/net if gross present
        gst_amount, net_amount = (0.0, 0.0)
        if gross_amount is not None:
            gst_amount, net_amount = gst_included_split(gross_amount, PROVINCE)

        # Normalize date
        if receipt_date:
            try:
                # try ISO first, else common formats
                dt = datetime.fromisoformat(receipt_date)
                receipt_date = dt.strftime('%Y-%m-%d')
            except Exception:
                for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%b %d, %Y', '%d-%b-%Y'):
                    try:
                        dt = datetime.strptime(receipt_date, fmt)
                        receipt_date = dt.strftime('%Y-%m-%d')
                        break
                    except Exception:
                        pass
        
        # Build output row with full receipts layout, defaulting to blanks
        out = {col: '' for col in receipts_cols}

        # Fill known/important fields if they exist in table
        def set_if_exists(col, value):
            if col in out and value is not None:
                out[col] = value

        set_if_exists('receipt_date', receipt_date)
        set_if_exists('vendor_name', vendor_name)
        set_if_exists('gross_amount', f"{gross_amount:.2f}" if isinstance(gross_amount, float) else (gross_amount or ''))
        set_if_exists('gst_amount', f"{gst_amount:.2f}")
        set_if_exists('net_amount', f"{net_amount:.2f}")
        set_if_exists('description', description)
        set_if_exists('category', category)
        set_if_exists('payment_method', payment_method)
        set_if_exists('comment', comment)
        set_if_exists('business_personal', business_personal)
        set_if_exists('employee_id', employee_id)
        set_if_exists('currency', DEFAULT_CURRENCY)
        set_if_exists('status', DEFAULT_STATUS)
        set_if_exists('source_system', DEFAULT_SOURCE_SYSTEM)
        set_if_exists('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # Create a stable source_reference if not provided
        if 'source_reference' in out and not out['source_reference']:
            out['source_reference'] = f"{receipt_date}_{vendor_name}_{gross_amount}"

        # Add source_hash if present
        if 'source_hash' in out:
            out['source_hash'] = build_source_hash(out)

        # Mark is_taxable if such a flag exists
        if 'is_taxable' in out and out['is_taxable'] in ('', None):
            out['is_taxable'] = 'true'

        out_rows.append(out)

    # Backup original CSV; if locked, fall back to alternate output path
    try:
        try:
            if os.path.exists(BACKUP_PATH):
                os.remove(BACKUP_PATH)
        except Exception:
            pass
        os.replace(CSV_PATH, BACKUP_PATH)
    except PermissionError:
        # File likely open/locked; write to a new file instead of replacing in-place
        global OUTPUT_PATH
        OUTPUT_PATH = r"l:\\limo\\mastercard_business_expenses_full.csv"
        print(f"WARNING: '{CSV_PATH}' appears to be in use; writing converted file to '{OUTPUT_PATH}' instead. No backup created.")

    # Write new CSV with full receipts layout
    with open(OUTPUT_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=receipts_cols)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Converted CSV to receipts layout with {len(out_rows)} rows.")
    if OUTPUT_PATH == CSV_PATH:
        print(f"Backup saved to: {BACKUP_PATH}")
    else:
        print(f"Output saved to: {OUTPUT_PATH}")

if __name__ == '__main__':
    main()
