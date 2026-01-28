import os
import psycopg2
from decimal import Decimal

DB = dict(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***'),
)

YEAR = 2012
MISMATCH_TOL = Decimal('1.00')

# Optional PD7A expected month values (e.g., August 2012)
PD7A_EXPECTED = {
    # month: expected aggregates for the entire company payroll
    8: {
        'gross': Decimal('14773.59'),
        'employee_cpp': Decimal('590.37'),
        'employer_cpp': Decimal('590.37'),
        'employee_ei': Decimal('198.50'),
        'employer_ei': Decimal('277.91'),
        'tax_deductions': Decimal('1341.63'),
        'total_remittance': Decimal('2998.78')
    }
}


def get_conn():
    return psycopg2.connect(**DB)


def get_cols(cur, table):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name=%s
    """, (table,))
    return {r[0] for r in cur.fetchall()}


def main():
    conn = get_conn(); cur = conn.cursor()

    cols = get_cols(cur, 'driver_payroll')

    # Column presence
    has_year = 'year' in cols
    has_month = 'month' in cols
    has_pay_date = 'pay_date' in cols
    has_employee_id = 'employee_id' in cols
    has_driver_id = 'driver_id' in cols

    gross_col = 'gross_pay' if 'gross_pay' in cols else None
    cpp_col = 'cpp' if 'cpp' in cols else None
    ei_col = 'ei' if 'ei' in cols else None
    tax_col = 'tax' if 'tax' in cols else None

    t4_14 = 't4_box_14' if 't4_box_14' in cols else None
    t4_16 = 't4_box_16' if 't4_box_16' in cols else None
    t4_18 = 't4_box_18' if 't4_box_18' in cols else None
    t4_22 = 't4_box_22' if 't4_box_22' in cols else None

    if not gross_col:
        print("ERROR: driver_payroll missing gross pay column"); return

    # Year filter
    # Optional payroll_class filter (exclude adjustments if present)
    has_payroll_class = 'payroll_class' in cols
    class_filter = " AND (payroll_class = 'WAGE' OR payroll_class IS NULL)" if has_payroll_class else ''

    if has_year:
        year_filter = f"year = {YEAR}"
        month_expr = 'month' if has_month else ("EXTRACT(MONTH FROM pay_date)" if has_pay_date else 'NULL')
        date_desc = 'year/month columns'
    elif has_pay_date:
        year_filter = f"pay_date >= '{YEAR}-01-01' AND pay_date < '{YEAR+1}-01-01'"
        month_expr = 'EXTRACT(MONTH FROM pay_date)'
        date_desc = 'pay_date column'
    else:
        print("ERROR: No year or pay_date columns available to filter 2012"); return

    print("="*80)
    print(f"DRIVER PAYROLL vs T4 ANALYSIS FOR {YEAR} ({date_desc})")
    print("="*80)

    # NULL employee_id rows
    if has_employee_id:
        cur.execute(f"SELECT COUNT(*) FROM driver_payroll WHERE {year_filter}{class_filter} AND employee_id IS NULL")
        null_emp = cur.fetchone()[0]
        print(f"Rows with NULL employee_id: {null_emp:,}")
    else:
        null_emp = None
        print("driver_payroll has no employee_id column")

    # Negative/zero irregularities
    cur.execute(f"""
        SELECT 
            COUNT(*) FILTER (WHERE {gross_col} <= 0) AS non_positive_gross,
            COUNT(*) FILTER (WHERE {cpp_col} < 0) AS neg_cpp,
            COUNT(*) FILTER (WHERE {ei_col} < 0) AS neg_ei,
            COUNT(*) FILTER (WHERE {tax_col} < 0) AS neg_tax
        FROM driver_payroll
        WHERE {year_filter}{class_filter}
    """)
    non_pos_gross, neg_cpp, neg_ei, neg_tax = cur.fetchone()
    print(f"Non-positive gross rows: {non_pos_gross:,}")
    print(f"Negative CPP rows: {neg_cpp:,}")
    print(f"Negative EI rows: {neg_ei:,}")
    print(f"Negative TAX rows: {neg_tax:,}")

    # Month coverage
    cur.execute(f"""
        SELECT {month_expr} AS m, COUNT(*)
        FROM driver_payroll
        WHERE {year_filter}{class_filter}
        GROUP BY 1
        ORDER BY 1
    """)
    print("\nMonth coverage (month -> rows):")
    month_counts = cur.fetchall()
    for m, cnt in month_counts:
        print(f"  {int(m) if m else 'NULL'} -> {cnt}")

    # Month aggregates for PD7A comparison (if columns present)
    if cpp_col and ei_col and tax_col:
        cur.execute(f"""
            SELECT {month_expr} AS m,
                   COALESCE(SUM({gross_col}),0) AS gross_sum,
                   COALESCE(SUM({cpp_col}),0) AS cpp_sum,
                   COALESCE(SUM({ei_col}),0) AS ei_sum,
                   COALESCE(SUM({tax_col}),0) AS tax_sum,
                   COUNT(DISTINCT {('employee_id' if has_employee_id else 'driver_id')}) AS employees_paid
            FROM driver_payroll
            WHERE {year_filter}{class_filter}
            GROUP BY 1
            ORDER BY 1
        """)
        month_aggs = {int(r[0]): r[1:] for r in cur.fetchall()}
        print("\nMonth aggregates (gross, cpp, ei, tax, employees_paid):")
        for m in sorted(month_aggs.keys()):
            g, c, e, t, emp_cnt = month_aggs[m]
            print(f"  {m:02d}: gross={Decimal(g):.2f} cpp={Decimal(c):.2f} ei={Decimal(e):.2f} tax={Decimal(t):.2f} employees={emp_cnt}")

        # PD7A verification for known months
        print("\nPD7A Verification (expected vs payroll, deltas):")
        for m, exp in PD7A_EXPECTED.items():
            if m not in month_aggs:
                print(f"  Month {m:02d}: no payroll data to compare")
                continue
            gross_sum, cpp_sum, ei_sum, tax_sum, emp_cnt = month_aggs[m]
            gross_sum = Decimal(gross_sum); cpp_sum = Decimal(cpp_sum); ei_sum = Decimal(ei_sum); tax_sum = Decimal(tax_sum)
            delta_gross = gross_sum - exp['gross']
            delta_cpp_emp = cpp_sum - exp['employee_cpp']
            delta_ei_emp = ei_sum - exp['employee_ei']
            delta_tax = tax_sum - exp['tax_deductions']
            # Employer EI theoretical = 1.4 × employee EI
            theo_employer_ei = (ei_sum * Decimal('1.4')).quantize(Decimal('0.01'))
            delta_employer_ei = theo_employer_ei - exp['employer_ei']
            # Employer CPP should match employee CPP
            delta_employer_cpp = cpp_sum - exp['employer_cpp']
            theoretical_total = (tax_sum + cpp_sum + ei_sum + cpp_sum + theo_employer_ei).quantize(Decimal('0.01'))
            delta_total = theoretical_total - exp['total_remittance']
            print(f"  Month {m:02d}: employees_paid={emp_cnt}")
            print(f"    Gross: payroll={gross_sum:.2f} expected={exp['gross']:.2f} delta={delta_gross:.2f}")
            print(f"    CPP (employee): payroll={cpp_sum:.2f} expected={exp['employee_cpp']:.2f} delta={delta_cpp_emp:.2f}")
            print(f"    CPP (employer same): payroll={cpp_sum:.2f} expected={exp['employer_cpp']:.2f} delta={delta_employer_cpp:.2f}")
            print(f"    EI (employee): payroll={ei_sum:.2f} expected={exp['employee_ei']:.2f} delta={delta_ei_emp:.2f}")
            print(f"    EI (employer theo 1.4x): theoretical={theo_employer_ei:.2f} expected={exp['employer_ei']:.2f} delta={delta_employer_ei:.2f}")
            print(f"    Tax: payroll={tax_sum:.2f} expected={exp['tax_deductions']:.2f} delta={delta_tax:.2f}")
            print(f"    Total theoretical remittance={theoretical_total:.2f} expected={exp['total_remittance']:.2f} delta={delta_total:.2f}")
    else:
        print("\nSkipping PD7A verification: missing one of cpp/ei/tax columns.")

    # Aggregate payroll by employee for YEAR
    emp_key = 'employee_id' if has_employee_id else ('driver_id' if has_driver_id else None)
    if not emp_key:
        print("ERROR: No employee_id or driver_id columns present"); return

    sum_cols = [gross_col]
    if cpp_col: sum_cols.append(cpp_col)
    if ei_col: sum_cols.append(ei_col)
    if tax_col: sum_cols.append(tax_col)

    select_sums = ', '.join([f"COALESCE(SUM({c}),0) AS sum_{c}" for c in sum_cols])

    cur.execute(f"""
        SELECT {emp_key}, {select_sums}
        FROM driver_payroll
        WHERE {year_filter}{class_filter}
        GROUP BY {emp_key}
    """)
    payroll_summaries = cur.fetchall()

    # T4 summaries per employee (take MAX of t4 boxes for the year)
    if all([t4_14, t4_16, t4_18, t4_22]):
        cur.execute(f"""
            SELECT {emp_key},
                   MAX({t4_14}) AS box14,
                   MAX({t4_16}) AS box16,
                   MAX({t4_18}) AS box18,
                   MAX({t4_22}) AS box22
            FROM driver_payroll
            WHERE {year_filter}{class_filter}
            GROUP BY {emp_key}
        """)
        t4_map = {r[0]: {'box14': r[1] or Decimal('0'), 'box16': r[2] or Decimal('0'), 'box18': r[3] or Decimal('0'), 'box22': r[4] or Decimal('0')} for r in cur.fetchall()}
    else:
        t4_map = {}
        print("Warning: Some T4 box columns missing; T4 comparison will be partial or skipped")

    # Compare per employee
    print("\n"+"-"*80)
    print("PER-EMPLOYEE T4 COMPARISON (differences > $1)")
    print("-"*80)

    mismatches = []
    for row in payroll_summaries:
        emp = row[0]
        sums = dict(zip([f'sum_{c}' for c in sum_cols], row[1:]))
        t4 = t4_map.get(emp)
        if not t4:
            # No T4 boxes present for this employee
            mismatches.append((emp, 'NO_T4', sums))
            continue
        diffs = {}
        if gross_col:
            diffs['box14_vs_gross'] = (Decimal(t4['box14']) - Decimal(sums[f'sum_{gross_col}']))
        if cpp_col:
            diffs['box16_vs_cpp'] = (Decimal(t4['box16']) - Decimal(sums[f'sum_{cpp_col}']))
        if ei_col:
            diffs['box18_vs_ei'] = (Decimal(t4['box18']) - Decimal(sums[f'sum_{ei_col}']))
        if tax_col:
            diffs['box22_vs_tax'] = (Decimal(t4['box22']) - Decimal(sums[f'sum_{tax_col}']))

        big = {k: v for k, v in diffs.items() if abs(v) > MISMATCH_TOL}
        if big:
            mismatches.append((emp, 'DIFF', big))

    if mismatches:
        for emp, kind, data in mismatches:
            if kind == 'NO_T4':
                print(f"Employee {emp}: NO T4 boxes present; payroll sums={data}")
            else:
                diffs_str = ', '.join([f"{k}={v:.2f}" for k,v in data.items()])
                print(f"Employee {emp}: {diffs_str}")
    else:
        print("No mismatches > $1 detected")

    # Totals summary
    print("\nTotals summary for "+str(YEAR)+":")
    cur.execute(f"""
        SELECT COALESCE(SUM({gross_col}),0) AS gross,
               COALESCE(SUM({cpp_col}),0) AS cpp,
               COALESCE(SUM({ei_col}),0) AS ei,
               COALESCE(SUM({tax_col}),0) AS tax
        FROM driver_payroll
        WHERE {year_filter}{class_filter}
    """)
    total_gross, total_cpp, total_ei, total_tax = cur.fetchone()
    print(f"  Payroll totals (WAGE filter{' on' if has_payroll_class else ' unavailable'}): gross={Decimal(total_gross):.2f}, cpp={Decimal(total_cpp):.2f}, ei={Decimal(total_ei):.2f}, tax={Decimal(total_tax):.2f}")

    if all([t4_14, t4_16, t4_18, t4_22]):
        cur.execute(f"""
            SELECT COALESCE(SUM({t4_14}),0), COALESCE(SUM({t4_16}),0),
                   COALESCE(SUM({t4_18}),0), COALESCE(SUM({t4_22}),0)
            FROM (
                SELECT {emp_key}, MAX({t4_14}) {t4_14}, MAX({t4_16}) {t4_16},
                       MAX({t4_18}) {t4_18}, MAX({t4_22}) {t4_22}
                FROM driver_payroll
                WHERE {year_filter}{class_filter}
                GROUP BY {emp_key}
            ) t
        """)
        t4_gross, t4_cpp, t4_ei, t4_tax = cur.fetchone()
        print(f"  T4 totals (sum of per-employee maxes): gross={Decimal(t4_gross):.2f}, cpp={Decimal(t4_cpp):.2f}, ei={Decimal(t4_ei):.2f}, tax={Decimal(t4_tax):.2f}")
        print(f"  Delta (T4 - payroll): gross={(Decimal(t4_gross)-Decimal(total_gross)):.2f}, cpp={(Decimal(t4_cpp)-Decimal(total_cpp)):.2f}, ei={(Decimal(t4_ei)-Decimal(total_ei)):.2f}, tax={(Decimal(t4_tax)-Decimal(total_tax)):.2f}")

    # Duplicate detection: exact duplicates on key fields
    key_fields = [emp_key]
    if has_year: key_fields.append('year')
    if has_month: key_fields.append('month')
    if has_pay_date and not has_month: key_fields.append('pay_date')
    for k in [gross_col, cpp_col, ei_col, tax_col]:
        if k: key_fields.append(k)
    key_expr = ', '.join(key_fields)

    cur.execute(f"""
        SELECT {key_expr}, COUNT(*) as cnt
        FROM driver_payroll
        WHERE {year_filter}{class_filter}
        GROUP BY {key_expr}
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC
        LIMIT 20
    """)
    dups = cur.fetchall()
    print("\nPotential duplicate groups (top 20):")
    if dups:
        for row in dups:
            *vals, cnt = row
            print(f"  cnt={cnt} | {vals}")
    else:
        print("  none")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
