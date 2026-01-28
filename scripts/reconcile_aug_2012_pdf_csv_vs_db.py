import csv
import os
import re
import psycopg2
from decimal import Decimal

DB = dict(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***'),
)

CSV_PATH = r"L:\limo\reports\pdf_employee_data_20251017_140241.csv"

NUM_RE = re.compile(r"-?\d{1,3}(?:[ ,]\d{3})*(?:[\.,]\d{2})|-?\d+(?:[\.,]\d{2})")

TARGET_DOCS = {
    'summary': 'August 2012 - Payroll Summary.pdf',
    'pdta': 'August 2012 PDTA Report.pdf'
}

KEY_PATTERNS = {
    'gross': re.compile(r"Gross\s+payroll\s+for\s+period", re.IGNORECASE),
    'cpp_emp': re.compile(r"CPP\s*-\s*Employee", re.IGNORECASE),
    'ei_emp': re.compile(r"EI\s*-\s*Employee", re.IGNORECASE),
    'tax_withheld': re.compile(r"(Employee\s+Taxes\s+Withheld|Tax\s+deductions)", re.IGNORECASE),
    'employees_paid': re.compile(r"No\.\s*of\s*employees\s*paid", re.IGNORECASE),
}


def to_decimal(token: str) -> Decimal:
    if token is None:
        return Decimal('0')
    s = token.replace(',', '').replace(' ', '')
    # normalize '14773 .59' cases
    s = s.replace('. ', '.')
    try:
        return Decimal(s)
    except Exception:
        # try replacing last space before 2 digits
        m = re.search(r"(\d+)\s(\d{2})$", s)
        if m:
            s2 = s[:m.start()] + '.' + m.group(2)
            return Decimal(s2)
        raise


def extract_numbers(field: str):
    return [to_decimal(m.group(0)) for m in NUM_RE.finditer(field)]


def read_pdf_csv_totals():
    results = {
        'gross': None,
        'cpp_emp': None,
        'ei_emp': None,
        'tax_withheld': None,
        'employees_paid': None,
    }
    with open(CSV_PATH, 'r', encoding='utf-8', errors='ignore', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 3:
                continue
            text, doc, _ = row[0], row[1], row[2] if len(row) > 2 else ''
            if TARGET_DOCS['summary'] in doc or TARGET_DOCS['pdta'] in doc:
                # Normalize patterns like '14773 .59' -> '14773.59'
                norm_text = re.sub(r"(\d)\s+\.(\d{2})", r"\1.\2", text)
                for key, pat in KEY_PATTERNS.items():
                    if pat.search(norm_text):
                        nums = extract_numbers(norm_text)
                        if key == 'employees_paid':
                            if nums:
                                results[key] = int(abs(nums[-1]))
                        else:
                            if nums:
                                # use last number on the line as the total (common pattern)
                                results[key] = abs(nums[-1])
    return results


def db_august_totals():
    conn = psycopg2.connect(**DB); cur = conn.cursor()
    cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='driver_payroll'""")
    cols = {r[0] for r in cur.fetchall()}
    gross_col = 'gross_pay'
    cpp_col = 'cpp' if 'cpp' in cols else None
    ei_col = 'ei' if 'ei' in cols else None
    tax_col = 'tax' if 'tax' in cols else None
    cur.execute(f"""
        SELECT COALESCE(SUM({gross_col}),0), COALESCE(SUM({cpp_col}),0), COALESCE(SUM({ei_col}),0), COALESCE(SUM({tax_col}),0), COUNT(DISTINCT employee_id)
        FROM driver_payroll
        WHERE year=2012 AND month=8
    """)
    g, c, e, t, n = cur.fetchone()
    cur.close(); conn.close()
    return Decimal(g), Decimal(c), Decimal(e), Decimal(t), n


def main():
    pdf_totals = read_pdf_csv_totals()
    print("PDF-derived August 2012 totals:")
    for k, v in pdf_totals.items():
        print(f"  {k}: {v}")

    g, c, e, t, n = db_august_totals()
    print("\nDB August 2012 totals (driver_payroll ALL classes):")
    print(f"  gross={g:.2f} cpp_emp={c:.2f} ei_emp={e:.2f} tax={t:.2f} employees={n}")

    # Deltas
    if pdf_totals['gross'] is not None:
        print(f"\nDelta gross = {g - pdf_totals['gross']:.2f}")
    if pdf_totals['cpp_emp'] is not None:
        print(f"Delta cpp_emp = {c - pdf_totals['cpp_emp']:.2f}")
    if pdf_totals['ei_emp'] is not None:
        print(f"Delta ei_emp = {e - pdf_totals['ei_emp']:.2f}")
    if pdf_totals['tax_withheld'] is not None:
        print(f"Delta tax = {t - pdf_totals['tax_withheld']:.2f}")
    if pdf_totals['employees_paid'] is not None:
        print(f"Delta employees = {n - pdf_totals['employees_paid']}")

if __name__ == '__main__':
    main()
