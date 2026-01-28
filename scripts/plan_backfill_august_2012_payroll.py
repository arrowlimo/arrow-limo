import os, csv, re, psycopg2, hashlib
from decimal import Decimal

DB = dict(host=os.getenv('DB_HOST','localhost'),database=os.getenv('DB_NAME','almsdata'),user=os.getenv('DB_USER','postgres'),password=os.getenv('DB_PASSWORD','***REMOVED***'))
CSV_PATH = r"L:\limo\reports\pdf_employee_data_20251017_140241.csv"
TARGET_DOC_SUMMARY = 'August 2012 - Payroll Summary.pdf'
TARGET_DOC_PDTA = 'August 2012 PDTA Report.pdf'

# Regex helpers
NUM_RE = re.compile(r"-?\d{1,3}(?:[ ,]\d{3})*(?:[\.,]\d{2})|-?\d+(?:[\.,]\d{2})")
NORMALIZE_DECIMAL_RE = re.compile(r"(\d)\s+\.(\d{2})")  # handles '14773 .59'

EXPECTED_TOTALS = {
    'gross': Decimal('14773.59'),
    'cpp_emp': Decimal('590.37'),
    'ei_emp': Decimal('198.50'),
    'tax_withheld': Decimal('2130.50'),
    'employees_paid': 11
}

# We will not insert anything. This script produces a safe plan.
# CONTRACT:
# Inputs: existing driver_payroll August 2012 data; OCR CSV summary lines.
# Outputs: per-component deltas, candidate per employee deltas (proportional), duplicate risk report.
# No writes; dry-run only. Use to design actual backfill.

RISK_NOTES = [
    "Do NOT backfill if an employee already has an identical (year,month,gross,cpp,ei,tax) tuple.",
    "Ensure payroll_class='BACKFILL' on inserts so future scripts can exclude or reclassify.",
    "Use a source_hash to guarantee idempotency (hash of employee_id|year|month|delta values).",
    "Skip employees whose delta would be < $0.50 after proportional allocation (treat as rounding).",
]

# Proportional allocation approach:
# Use existing August gross distribution as weights to allocate missing gross delta; then scale CPP/EI/Tax by same factor
# This preserves relative shape while preventing duplication. Can be refined later using per column values from PDF once mapping confirmed.

EMP_WEIGHT_MIN_THRESHOLD = Decimal('10')  # employees with < $10 gross existing get minimal allocation (flagged)
ROUND = lambda x: (x.quantize(Decimal('0.01')) if isinstance(x, Decimal) else Decimal(str(x)).quantize(Decimal('0.01')))


def dec(token: str) -> Decimal:
    token = token.replace(',', '').replace(' ', '')
    token = token.replace('.-', '.0') if token.endswith('.-') else token
    try:
        return Decimal(token)
    except Exception:
        m = re.search(r"(\d+)\.(\d{1})$", token)
        if m:
            return Decimal(m.group(1) + m.group(2) + '0')
        raise


def extract_numbers(text: str):
    norm = NORMALIZE_DECIMAL_RE.sub(r"\1.\2", text)
    return [dec(m.group(0)) for m in NUM_RE.finditer(norm)]


def read_pdf_totals():
    totals = {'gross': None, 'cpp_emp': None, 'ei_emp': None, 'tax_withheld': None}
    with open(CSV_PATH,'r',encoding='utf-8',errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2: continue
            text, doc = row[0], row[1]
            if TARGET_DOC_SUMMARY in doc or TARGET_DOC_PDTA in doc:
                # detect key phrases
                if 'Gross payroll for period' in text:
                    nums = extract_numbers(text)
                    if nums: totals['gross'] = abs(nums[-1])
                elif 'CPP - Employee' in text and '(' not in text:  # summary total line
                    nums = extract_numbers(text)
                    if nums: totals['cpp_emp'] = abs(nums[-1])
                elif 'EI - Employee' in text and '(' not in text:
                    nums = extract_numbers(text)
                    if nums: totals['ei_emp'] = abs(nums[-1])
                elif 'Employee Taxes Withheld' in text or 'Tax deductions' in text:
                    nums = extract_numbers(text)
                    if nums: totals['tax_withheld'] = abs(nums[-1])
    return totals


def get_db_august(conn):
    cur = conn.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='driver_payroll'")
    cols = {r[0] for r in cur.fetchall()}
    gross_col = 'gross_pay'
    cpp_col = 'cpp' if 'cpp' in cols else None
    ei_col = 'ei' if 'ei' in cols else None
    tax_col = 'tax' if 'tax' in cols else None

    cur.execute(f"""
        SELECT employee_id, COALESCE(SUM({gross_col}),0) g,
               COALESCE(SUM({cpp_col}),0), COALESCE(SUM({ei_col}),0), COALESCE(SUM({tax_col}),0), COUNT(*) cnt
        FROM driver_payroll
        WHERE year=2012 AND month=8 AND (payroll_class='WAGE' OR payroll_class IS NULL OR payroll_class='BACKFILL')
        GROUP BY employee_id
    """)
    rows = cur.fetchall()
    cur.close()
    return rows, gross_col, cpp_col, ei_col, tax_col


def compute_plan():
    conn = psycopg2.connect(**DB)
    rows, gross_col, cpp_col, ei_col, tax_col = get_db_august(conn)
    pdf_totals = read_pdf_totals()

    existing_gross_total = sum(r[1] for r in rows)
    existing_cpp_total = sum(r[2] for r in rows)
    existing_ei_total = sum(r[3] for r in rows)
    existing_tax_total = sum(r[4] for r in rows)

    deltas = {
        'gross': (pdf_totals['gross'] - existing_gross_total) if pdf_totals['gross'] else None,
        'cpp_emp': (pdf_totals['cpp_emp'] - existing_cpp_total) if pdf_totals['cpp_emp'] else None,
        'ei_emp': (pdf_totals['ei_emp'] - existing_ei_total) if pdf_totals['ei_emp'] else None,
        'tax_withheld': (pdf_totals['tax_withheld'] - existing_tax_total) if pdf_totals['tax_withheld'] else None,
    }

    print("Existing vs PDF Totals (August 2012):")
    print(f"  Gross: DB={existing_gross_total:.2f} PDF={pdf_totals['gross']:.2f} Delta={deltas['gross']:.2f}")
    print(f"  CPP Emp: DB={existing_cpp_total:.2f} PDF={pdf_totals['cpp_emp']:.2f} Delta={deltas['cpp_emp']:.2f}")
    print(f"  EI Emp: DB={existing_ei_total:.2f} PDF={pdf_totals['ei_emp']:.2f} Delta={deltas['ei_emp']:.2f}")
    print(f"  Tax: DB={existing_tax_total:.2f} PDF={pdf_totals['tax_withheld']:.2f} Delta={deltas['tax_withheld']:.2f}")

    if any(d is None or d <= 0 for d in deltas.values()):
        print("\nNo positive deltas requiring backfill or PDF totals incomplete - aborting allocation.")
        return

    # Weight employees by existing gross
    weights = []
    for emp_id, gross, cpp, ei, tax, cnt in rows:
        w = gross if gross > 0 else Decimal('0')
        weights.append((emp_id, gross, w))
    total_weight = sum(w for _,_,w in weights)
    if total_weight <= 0:
        print("All existing gross are zero; cannot allocate proportionally.")
        return

    print("\nProposed per-employee backfill (proportional):")
    plan_rows = []
    for emp_id, gross, w in weights:
        proportion = (w / total_weight) if total_weight else Decimal('0')
        delta_g = ROUND(deltas['gross'] * proportion)
        delta_cpp = ROUND(deltas['cpp_emp'] * proportion)
        delta_ei = ROUND(deltas['ei_emp'] * proportion)
        delta_tax = ROUND(deltas['tax_withheld'] * proportion)
        risk_flags = []
        if gross < EMP_WEIGHT_MIN_THRESHOLD:
            risk_flags.append('LOW_BASE_GROSS')
        if delta_g < Decimal('0.50'):
            risk_flags.append('TINY_DELTA_SKIP')
        # Build hash for idempotency
        h_source = f"{emp_id}|2012|8|{delta_g}|{delta_cpp}|{delta_ei}|{delta_tax}".encode('utf-8')
        source_hash = hashlib.sha256(h_source).hexdigest()[:16]
        plan_rows.append((emp_id, delta_g, delta_cpp, delta_ei, delta_tax, source_hash, ','.join(risk_flags)))
        print(f"  emp={emp_id} gross_delta={delta_g:.2f} cpp_delta={delta_cpp:.2f} ei_delta={delta_ei:.2f} tax_delta={delta_tax:.2f} hash={source_hash} flags={risk_flags or 'OK'}")

    # Integrity check sum
    sum_g = sum(r[1] for r in plan_rows if 'TINY_DELTA_SKIP' not in r[6])
    sum_cpp = sum(r[2] for r in plan_rows if 'TINY_DELTA_SKIP' not in r[6])
    sum_ei = sum(r[3] for r in plan_rows if 'TINY_DELTA_SKIP' not in r[6])
    sum_tax = sum(r[4] for r in plan_rows if 'TINY_DELTA_SKIP' not in r[6])
    print("\nAllocation summary (excluding tiny skips):")
    print(f"  gross_allocated={sum_g:.2f} vs delta_gross={deltas['gross']:.2f}")
    print(f"  cpp_allocated={sum_cpp:.2f} vs delta_cpp={deltas['cpp_emp']:.2f}")
    print(f"  ei_allocated={sum_ei:.2f} vs delta_ei={deltas['ei_emp']:.2f}")
    print(f"  tax_allocated={sum_tax:.2f} vs delta_tax={deltas['tax_withheld']:.2f}")

    print("\nDuplicate Risk & Safeguards:")
    for note in RISK_NOTES:
        print(f"  - {note}")

    print("\nSuggested INSERT template (DO NOT EXECUTE YET):")
    print("  INSERT INTO driver_payroll (employee_id, year, month, gross_pay, cpp, ei, tax, payroll_class, source)")
    print("    VALUES (..., 2012, 8, delta_g, delta_cpp, delta_ei, delta_tax, 'BACKFILL', 'PDF_SUMMARY');")
    print("  -- Add source_hash column if available for idempotency")

if __name__ == '__main__':
    compute_plan()
