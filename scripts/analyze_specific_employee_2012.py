import os, psycopg2, math
from decimal import Decimal, ROUND_HALF_UP

DB = dict(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REMOVED***'),
)

YEAR = 2012
TARGET_NAME_PART = 'Jeannie'  # case-insensitive match
CPP_RATE_2012 = Decimal('0.0495')
CPP_BASIC_EXEMPT_ANNUAL = Decimal('3500')
EI_RATE_2012 = Decimal('0.0183')
EI_MAX_ANNUAL = Decimal('45900')


def get_conn():
    return psycopg2.connect(**DB)


def dec(x):
    return Decimal(str(x)) if x is not None else Decimal('0')


def round_money(d):
    return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def main():
    conn = get_conn(); cur = conn.cursor()

    # Find employee(s) matching name fragment
    cur.execute("""
        SELECT employee_id, full_name
        FROM employees
        WHERE LOWER(full_name) LIKE LOWER(%s)
        ORDER BY employee_id
    """, (f'%{TARGET_NAME_PART}%',))
    matches = cur.fetchall()
    if not matches:
        print(f"No employees found matching '{TARGET_NAME_PART}'")
        return
    print("Matched employees:")
    for eid, name in matches:
        print(f"  employee_id={eid} name={name}")

    employee_ids = [m[0] for m in matches]

    # Determine if payroll_class exists
    cur.execute("""SELECT column_name FROM information_schema.columns WHERE table_name='driver_payroll'""")
    cols = {r[0] for r in cur.fetchall()}
    has_year = 'year' in cols
    has_month = 'month' in cols
    has_payroll_class = 'payroll_class' in cols

    gross_col = 'gross_pay'
    cpp_col = 'cpp' if 'cpp' in cols else None
    ei_col = 'ei' if 'ei' in cols else None
    tax_col = 'tax' if 'tax' in cols else None

    class_filter = " AND (payroll_class = 'WAGE' OR payroll_class IS NULL)" if has_payroll_class else ''

    if not has_year:
        print("driver_payroll missing 'year' column – aborting targeted year analysis")
        return

    # Pull all rows for these employees in YEAR
    cur.execute(f"""
        SELECT employee_id, month, {gross_col}, {cpp_col}, {ei_col}, {tax_col}
        FROM driver_payroll
        WHERE year=%s{class_filter} AND employee_id = ANY(%s)
        ORDER BY employee_id, month
    """, (YEAR, employee_ids))
    rows = cur.fetchall()
    if not rows:
        print("No payroll rows for target employees in year")
        return

    # Aggregate per month per employee
    from collections import defaultdict
    monthly = defaultdict(lambda: defaultdict(lambda: {'gross':Decimal('0'), 'cpp':Decimal('0'), 'ei':Decimal('0'), 'tax':Decimal('0'), 'count':0}))

    for eid, month, gross, cpp, ei, tax in rows:
        d = monthly[eid][int(month)]
        d['gross'] += dec(gross)
        if cpp_col: d['cpp'] += dec(cpp)
        if ei_col: d['ei'] += dec(ei)
        if tax_col: d['tax'] += dec(tax)
        d['count'] += 1

    print(f"\nPayroll aggregation for {YEAR} (post WAGE filter if present):")
    for eid in employee_ids:
        print(f"\nEmployee {eid}")
        for m in sorted(monthly[eid].keys()):
            data = monthly[eid][m]
            # Theoretical CPP/EI for the MONTH (approx) using monthly basic exemption
            monthly_basic_exempt = CPP_BASIC_EXEMPT_ANNUAL / Decimal('12')
            pensionable = (data['gross'] - monthly_basic_exempt)
            if pensionable < 0: pensionable = Decimal('0')
            theoretical_cpp = round_money(pensionable * CPP_RATE_2012)
            # EI theoretical unless near cap
            # Need cumulative YTD to test cap
        
        # Build cumulative for cap test
    
    # Build cumulative YTD per employee for EI testing and re-output with theory
    for eid in employee_ids:
        cum_gross = Decimal('0')
        cum_ei_insurable = Decimal('0')
        print(f"\nEmployee {eid} monthly detail with theoretical CPP/EI:")
        for m in sorted(monthly[eid].keys()):
            data = monthly[eid][m]
            cum_gross += data['gross']
            # Assume full gross insurable unless cap reached
            remaining_insurable_cap = EI_MAX_ANNUAL - cum_ei_insurable
            insurable_this_month = min(data['gross'], remaining_insurable_cap) if remaining_insurable_cap > 0 else Decimal('0')
            cum_ei_insurable += insurable_this_month
            monthly_basic_exempt = CPP_BASIC_EXEMPT_ANNUAL / Decimal('12')
            pensionable = max(data['gross'] - monthly_basic_exempt, Decimal('0'))
            theoretical_cpp = round_money(pensionable * CPP_RATE_2012)
            theoretical_ei = round_money(insurable_this_month * EI_RATE_2012)
            print(f"  M{m:02d} count={data['count']:2d} gross={data['gross']:.2f} cpp={data['cpp']:.2f} theo_cpp={theoretical_cpp:.2f} ei={data['ei']:.2f} theo_ei={theoretical_ei:.2f} tax={data['tax']:.2f}")

    # Summaries
    for eid in employee_ids:
        gross_total = sum(monthly[eid][m]['gross'] for m in monthly[eid])
        cpp_total = sum(monthly[eid][m]['cpp'] for m in monthly[eid])
        ei_total = sum(monthly[eid][m]['ei'] for m in monthly[eid])
        tax_total = sum(monthly[eid][m]['tax'] for m in monthly[eid])
        print(f"\nEmployee {eid} totals: gross={gross_total:.2f} cpp={cpp_total:.2f} ei={ei_total:.2f} tax={tax_total:.2f}")

    # Focus on month 8 (August) for Jeannie example if present
    for eid in employee_ids:
        if 8 in monthly[eid]:
            d = monthly[eid][8]
            print(f"\nEmployee {eid} August gross={d['gross']:.2f} cpp={d['cpp']:.2f} ei={d['ei']:.2f} tax={d['tax']:.2f}")

    cur.close(); conn.close()

if __name__ == '__main__':
    main()
