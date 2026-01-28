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

EXPECTED_PD7A = {
    'gross': Decimal('14773.59'),
    'employee_cpp': Decimal('590.37'),
    'employee_ei': Decimal('198.50'),
    'tax_deductions': Decimal('1341.63'),
    'employer_cpp': Decimal('590.37'),
    'employer_ei': Decimal('277.91'),
    'total_remittance': Decimal('2998.78')
}

# PDF file list provided (August 31 2012 pay date)
PDF_FILES = [
    r"L:\limo\pdf\Doug Redmond  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Zak Keller  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Dale Menard  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Paul Mansell  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Dustan Townsend  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Angel Escobar  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Chantal Thomas  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Michael Richard  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\Jesse Gordon  -(EE)-PDOC-Date paid- 2012-08-31_ocred.pdf",
    r"L:\limo\pdf\August 2012 - Payroll Summary_ocred (1).pdf",
    r"L:\limo\pdf\August.2012-Paul Pay Cheque_ocred (1).pdf"
]

# Normalize employee names from PDF filenames to match employees.full_name pattern ("Last, First")

def extract_names_from_pdfs():
    names = []
    pattern = re.compile(r"([^\\/]+?)\s+-\(EE\)-PDOC-Date paid-\s+2012-08-31", re.IGNORECASE)
    for path in PDF_FILES:
        fname = os.path.basename(path)
        m = pattern.search(fname)
        if m:
            raw = m.group(1).strip()
            # raw is like "Doug Redmond" -> convert to "Redmond, Doug"
            parts = raw.split()
            if len(parts) >= 2:
                first = parts[0]
                last = ' '.join(parts[1:])
                names.append((raw, f"{last}, {first}"))
    return names


def get_conn():
    return psycopg2.connect(**DB)


def main():
    pdf_name_map = extract_names_from_pdfs()
    print("PDF-derived employee names (raw -> normalized):")
    for raw, norm in pdf_name_map:
        print(f"  {raw} -> {norm}")

    norm_names = [n for _, n in pdf_name_map]
    conn = get_conn(); cur = conn.cursor()

    # Build lookup from employees
    cur.execute("SELECT employee_id, full_name FROM employees")
    emp_rows = cur.fetchall()
    name_to_id = {full.strip().lower(): eid for eid, full in emp_rows}

    matched_ids = []
    missing = []
    for raw, norm in pdf_name_map:
        eid = name_to_id.get(norm.lower())
        if eid:
            matched_ids.append(eid)
        else:
            missing.append(norm)
    print("\nMatched employee_ids:")
    for eid in matched_ids:
        print(f"  {eid}")
    if missing:
        print("Missing (not found in employees table):")
        for n in missing:
            print(f"  {n}")

    # Introspect driver_payroll columns
    cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='driver_payroll'""")
    cols = {r[0] for r in cur.fetchall()}
    if 'year' not in cols or 'month' not in cols:
        print("driver_payroll missing year/month columns; aborting.")
        return

    gross_col = 'gross_pay'
    cpp_col = 'cpp' if 'cpp' in cols else None
    ei_col = 'ei' if 'ei' in cols else None
    tax_col = 'tax' if 'tax' in cols else None
    has_payroll_class = 'payroll_class' in cols

    # Aggregate August WITH and WITHOUT WAGE filter
    filters = [
        ("WAGE_ONLY", "AND (payroll_class='WAGE' OR payroll_class IS NULL)" if has_payroll_class else ''),
        ("ALL_CLASSES", "")
    ]

    results = {}
    for tag, extra in filters:
        cur.execute(f"""
            SELECT COALESCE(SUM({gross_col}),0) AS gross,
                   COALESCE(SUM({cpp_col}),0) AS cpp,
                   COALESCE(SUM({ei_col}),0) AS ei,
                   COALESCE(SUM({tax_col}),0) AS tax,
                   COUNT(DISTINCT employee_id) AS employees
            FROM driver_payroll
            WHERE year=2012 AND month=8 {extra}
        """)
        results[tag] = cur.fetchone()

    print("\nAugust 2012 aggregates:")
    for tag, row in results.items():
        gross, cpp, ei, tax, emp_cnt = row
        print(f"  {tag}: gross={Decimal(gross):.2f} cpp={Decimal(cpp):.2f} ei={Decimal(ei):.2f} tax={Decimal(tax):.2f} employees={emp_cnt}")

    # Breakdown of non-WAGE contribution if payroll_class present
    if has_payroll_class:
        cur.execute(f"""
            SELECT payroll_class, COALESCE(SUM({gross_col}),0) g, COALESCE(SUM({cpp_col}),0) c, COALESCE(SUM({ei_col}),0) e, COALESCE(SUM({tax_col}),0) t
            FROM driver_payroll
            WHERE year=2012 AND month=8
            GROUP BY payroll_class
            ORDER BY payroll_class NULLS LAST
        """)
        print("\nAugust 2012 by payroll_class:")
        for pc, g, c, e, t in cur.fetchall():
            print(f"  class={pc or 'NULL':10s} gross={Decimal(g):.2f} cpp={Decimal(c):.2f} ei={Decimal(e):.2f} tax={Decimal(t):.2f}")

    # Compare ALL_CLASSES to PD7A
    all_gross, all_cpp, all_ei, all_tax, emp_cnt = results['ALL_CLASSES']
    all_gross = Decimal(all_gross); all_cpp = Decimal(all_cpp); all_ei = Decimal(all_ei); all_tax = Decimal(all_tax)

    print("\nPD7A Comparison (ALL_CLASSES vs expected):")
    def delta(label, actual, expected):
        return f"{label}: actual={actual:.2f} expected={expected:.2f} delta={(actual-expected):.2f}"

    print("  "+delta('Gross', all_gross, EXPECTED_PD7A['gross']))
    print("  "+delta('CPP employee', all_cpp, EXPECTED_PD7A['employee_cpp']))
    print("  "+delta('EI employee', all_ei, EXPECTED_PD7A['employee_ei']))
    print("  "+delta('Tax', all_tax, EXPECTED_PD7A['tax_deductions']))

    # Theoretical employer portions
    theo_employer_cpp = all_cpp  # 1:1
    theo_employer_ei = (all_ei * Decimal('1.4')).quantize(Decimal('0.01'))
    theoretical_total = (all_tax + all_cpp + all_ei + theo_employer_cpp + theo_employer_ei).quantize(Decimal('0.01'))

    print("  "+delta('Employer CPP (theo)', theo_employer_cpp, EXPECTED_PD7A['employer_cpp']))
    print("  "+delta('Employer EI (theo 1.4x)', theo_employer_ei, EXPECTED_PD7A['employer_ei']))
    print("  "+delta('Total remittance (theo)', theoretical_total, EXPECTED_PD7A['total_remittance']))

    # If large deficits remain, list top missing gross employees (compare to expected if possible)
    if all_gross < EXPECTED_PD7A['gross'] * Decimal('0.9'):
        cur.execute(f"""
            SELECT dp.employee_id, e.full_name, COALESCE(SUM({gross_col}),0) g
            FROM driver_payroll dp
            LEFT JOIN employees e ON e.employee_id = dp.employee_id
            WHERE dp.year=2012 AND dp.month=8
            GROUP BY dp.employee_id, e.full_name
            ORDER BY g DESC
        """)
        print("\nEmployee gross ranking (August 2012 ALL_CLASSES):")
        for eid, name, g in cur.fetchall():
            print(f"  employee_id={eid} name={name or 'UNKNOWN'} gross={Decimal(g):.2f}")

    conn.close()

if __name__ == '__main__':
    main()
