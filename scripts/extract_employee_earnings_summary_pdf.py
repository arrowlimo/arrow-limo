import os
import re
import pdfplumber
import psycopg2

PG_DB = os.getenv('PGDATABASE', 'almsdata')
PG_USER = os.getenv('PGUSER', 'postgres')
PG_HOST = os.getenv('PGHOST', 'localhost')
PG_PORT = os.getenv('PGPORT', '5432')
PG_PASSWORD = os.getenv('PGPASSWORD', '***REMOVED***')

COLUMNS = [
    'salary', 'wages', 'wages_other', 'gratuities_taxable', 'gratuities_nontaxable',
    'expense_reimburse', 'federal_income_tax', 'cpp_employee', 'cpp_company',
    'ei_employee', 'ei_company', 'vacpay_accrued', 'vacpay_accrual_paid_out',
    'vacpay_paid_out', 'total'
]

MONTH_NAMES = ['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']

def connect_db():
    return psycopg2.connect(
        dbname=PG_DB, user=PG_USER, host=PG_HOST, port=PG_PORT, password=PG_PASSWORD
    )

def create_table():
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS staging_employee_pay_summary (
            id SERIAL PRIMARY KEY,
            year INTEGER,
            employee_name VARCHAR(255),
            salary NUMERIC(12,2),
            wages NUMERIC(12,2),
            wages_other NUMERIC(12,2),
            gratuities_taxable NUMERIC(12,2),
            gratuities_nontaxable NUMERIC(12,2),
            expense_reimburse NUMERIC(12,2),
            federal_income_tax NUMERIC(12,2),
            cpp_employee NUMERIC(12,2),
            cpp_company NUMERIC(12,2),
            ei_employee NUMERIC(12,2),
            ei_company NUMERIC(12,2),
            vacpay_accrued NUMERIC(12,2),
            vacpay_accrual_paid_out NUMERIC(12,2),
            vacpay_paid_out NUMERIC(12,2),
            total NUMERIC(12,2),
            source_file VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    cur.close()
    conn.close()


def parse_amount(tok: str):
    if tok is None:
        return None
    s = tok.strip().replace(',', '')
    if not s:
        return None
    # Convert trailing negative style (e.g. 200-) to -200
    neg = False
    if s.endswith('-') and s[:-1].replace('.', '', 1).isdigit():
        neg = True
        s = s[:-1]
    # Sometimes amounts paste without last digit; if only one decimal place, pad to 2
    if re.match(r'^-?\d+\.\d$', s):
        s = f"{s}0"
    m = re.match(r'^-?\d+(?:\.\d{2})?$', s)
    if not m:
        return None
    val = float(s)
    if neg:
        val = -val
    # Ensure 2 decimals by rounding
    return round(val, 2)


def extract_records(pdf_path):
    year = None
    m = re.search(r'(20\d{2})', os.path.basename(pdf_path))
    if m:
        year = int(m.group(1))

    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for raw in text.split('\n'):
                line = raw.strip()
                if not line:
                    continue
                # Skip headers/labels
                low = line.lower()
                if any(k in low for k in ['employee', 'earnings', 'salary', 'wages', 'gratuities', 'cpp', 'ei']) and '-' not in line:
                    # might be header rows; continue scanning
                    pass
                # Pattern: Name- followed by a lot of numbers ending with TOTAL
                if '-' in line:
                    name_part, nums_part = line.split('-', 1)
                    name = name_part.strip()
                    # Tokenize numbers
                    tokens = re.findall(r'[\d,]+\.\d{1,2}-?|\d+\.?\d{0,2}-?', nums_part)
                    amounts = [parse_amount(t) for t in tokens]
                    # Need at least as many columns as defined
                    if len(amounts) >= len(COLUMNS):
                        # Take the last len(COLUMNS) amounts to align with expected columns
                        selected = amounts[-len(COLUMNS):]
                        rec = {'year': year, 'employee_name': name}
                        for col, val in zip(COLUMNS, selected):
                            rec[col] = val
                        rows.append(rec)
    return rows


def insert_records(rows, source_file):
    if not rows:
        print(f"No summary rows found in {source_file}")
        return
    conn = connect_db()
    cur = conn.cursor()
    for r in rows:
        cur.execute(
            f"""
            INSERT INTO staging_employee_pay_summary (
                year, employee_name, {', '.join(COLUMNS)}, source_file
            ) VALUES (
                %s, %s, {', '.join(['%s'] * len(COLUMNS))}, %s
            )
            """,
            [r.get('year'), r.get('employee_name')] + [r.get(c) for c in COLUMNS] + [source_file]
        )
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(rows)} rows from {source_file}")


def mark_excluded(file_path):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE staging_driver_pay_files
        SET status = 'excluded', file_type = 'pay_summary',
            error_message = 'Reference data: Employee Earnings Summary extracted to staging_employee_pay_summary'
        WHERE file_path = %s
        """,
        (file_path,)
    )
    conn.commit()
    cur.close()
    conn.close()


def main():
    create_table()
    # Known file (2014 example) and any others matching pattern in quickbooks dirs
    candidates = [
        r"L:\\limo\\quickbooks\\New folder\\2014 Employee Earnings Sum..pdf",
    ]
    import glob
    more = glob.glob(r"L:\\limo\\quickbooks\\**\\*Employee*Earnings*Sum*.pdf", recursive=True)
    for f in more:
        if f not in candidates:
            candidates.append(f)

    for pdf_path in candidates:
        if os.path.exists(pdf_path):
            print(f"\nProcessing: {pdf_path}")
            rows = extract_records(pdf_path)
            insert_records(rows, pdf_path)
            mark_excluded(pdf_path)
        else:
            print(f"Missing: {pdf_path}")

if __name__ == '__main__':
    main()
