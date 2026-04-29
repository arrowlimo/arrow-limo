from decimal import Decimal
import json
import psycopg2
from psycopg2.extras import RealDictCursor

DB = dict(host='localhost', dbname='almsdata', user='postgres', password='ArrowLimousine', port=5432)
PAUL_EMP_ID = 10
YEARS = [2012, 2013, 2014]


def table_exists(cur, table_name):
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (table_name,),
    )
    return cur.fetchone()['exists']


def get_columns(cur, table_name):
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [row['column_name'] for row in cur.fetchall()]


def fetch_all(cur, query, params=None):
    cur.execute(query, params or ())
    return cur.fetchall()


def audit_employee(cur):
    cols = get_columns(cur, 'employees')
    selectable = [c for c in ['employee_id', 'employee_number', 'full_name', 'first_name', 'last_name', 't4_sin', 'sin', 'street_address', 'city', 'province', 'postal_code'] if c in cols]
    cur.execute(f"SELECT {', '.join(selectable)} FROM employees WHERE employee_id = %s", (PAUL_EMP_ID,))
    return dict(cur.fetchone()), cols


def audit_employee_t4_records(cur):
    table = 'employee_t4_records'
    if not table_exists(cur, table):
        return None
    cols = set(get_columns(cur, table))
    wanted = [
        'tax_year', 'employee_id', 't4_id',
        'box_14_employment_income', 'box_16_cpp_contributions', 'box_18_ei_premiums',
        'box_22_income_tax', 'box_24_ei_insurable_earnings', 'box_26_cpp_pensionable_earnings',
        'box_12_taxable_benefits', 'notes'
    ]
    select_cols = [c for c in wanted if c in cols]
    rows = fetch_all(
        cur,
        f"SELECT {', '.join(select_cols)} FROM {table} WHERE employee_id = %s AND tax_year >= 2012 ORDER BY tax_year",
        (PAUL_EMP_ID,),
    )
    return [dict(r) for r in rows]


def audit_employee_t4_summary(cur):
    table = 'employee_t4_summary'
    if not table_exists(cur, table):
        return None
    cols = set(get_columns(cur, table))
    year_col = 'fiscal_year' if 'fiscal_year' in cols else ('tax_year' if 'tax_year' in cols else None)
    if not year_col or 'employee_id' not in cols:
        return {'columns': sorted(cols), 'rows': []}
    wanted = [
        'employee_id', year_col,
        'box14', 'box16', 'box18', 'box22', 'box24', 'box26',
        't4_box_14', 't4_box_16', 't4_box_18', 't4_box_22', 't4_box_24', 't4_box_26',
        'employment_income', 'cpp_contributions', 'ei_premiums', 'income_tax', 'ei_insurable', 'cpp_pensionable'
    ]
    select_cols = [c for c in wanted if c in cols]
    rows = fetch_all(
        cur,
        f"SELECT {', '.join(select_cols)} FROM {table} WHERE employee_id = %s AND {year_col} >= 2012 ORDER BY {year_col}",
        (PAUL_EMP_ID,),
    )
    return {'columns': sorted(cols), 'rows': [dict(r) for r in rows]}


def summarize_employee_pay_master(cur):
    table = 'employee_pay_master'
    if not table_exists(cur, table):
        return None
    cols = set(get_columns(cur, table))
    if 'employee_id' not in cols or 'fiscal_year' not in cols:
        return {'columns': sorted(cols), 'rows': []}
    gross_col = 'gross_pay' if 'gross_pay' in cols else None
    cpp_col = 'cpp_employee' if 'cpp_employee' in cols else None
    ei_col = 'ei_employee' if 'ei_employee' in cols else None
    tax_col = 'total_income_tax' if 'total_income_tax' in cols else None
    parts = ['fiscal_year AS year', 'COUNT(*) AS row_count']
    if gross_col:
        parts.append(f'COALESCE(SUM({gross_col}), 0) AS gross_pay')
    if cpp_col:
        parts.append(f'COALESCE(SUM({cpp_col}), 0) AS cpp')
    if ei_col:
        parts.append(f'COALESCE(SUM({ei_col}), 0) AS ei')
    if tax_col:
        parts.append(f'COALESCE(SUM({tax_col}), 0) AS income_tax')
    rows = fetch_all(
        cur,
        f"SELECT {', '.join(parts)} FROM {table} WHERE employee_id = %s AND fiscal_year >= 2012 GROUP BY fiscal_year ORDER BY fiscal_year",
        (PAUL_EMP_ID,),
    )
    return {'columns': sorted(cols), 'rows': [dict(r) for r in rows]}


def summarize_driver_payroll(cur):
    table = 'driver_payroll'
    if not table_exists(cur, table):
        return None
    cols = set(get_columns(cur, table))
    if 'employee_id' not in cols:
        return {'columns': sorted(cols), 'rows': []}
    year_expr = None
    if 'year' in cols:
        year_expr = 'year'
    elif 'pay_date' in cols:
        year_expr = 'EXTRACT(YEAR FROM pay_date)::int'
    if not year_expr:
        return {'columns': sorted(cols), 'rows': []}
    gross_col = 'gross_pay' if 'gross_pay' in cols else None
    cpp_col = 'cpp' if 'cpp' in cols else None
    ei_col = 'ei' if 'ei' in cols else None
    tax_col = 'tax' if 'tax' in cols else None
    t4_14 = 't4_box_14' if 't4_box_14' in cols else None
    parts = [f'{year_expr} AS year', 'COUNT(*) AS row_count']
    if gross_col:
        parts.append(f'COALESCE(SUM({gross_col}), 0) AS gross_pay')
    if cpp_col:
        parts.append(f'COALESCE(SUM({cpp_col}), 0) AS cpp')
    if ei_col:
        parts.append(f'COALESCE(SUM({ei_col}), 0) AS ei')
    if tax_col:
        parts.append(f'COALESCE(SUM({tax_col}), 0) AS income_tax')
    if t4_14:
        parts.append(f'MAX({t4_14}) AS t4_box_14')
    rows = fetch_all(
        cur,
        f"SELECT {', '.join(parts)} FROM {table} WHERE employee_id = %s AND {year_expr} >= 2012 GROUP BY {year_expr} ORDER BY {year_expr}",
        (PAUL_EMP_ID,),
    )
    return {'columns': sorted(cols), 'rows': [dict(r) for r in rows]}


def summarize_generic_year_table(cur, table_name, year_col, gross_col):
    if not table_exists(cur, table_name):
        return None
    cols = set(get_columns(cur, table_name))
    if 'employee_id' not in cols or year_col not in cols or gross_col not in cols:
        return {'columns': sorted(cols), 'rows': []}
    rows = fetch_all(
        cur,
        f"SELECT {year_col} AS year, COUNT(*) AS row_count, COALESCE(SUM({gross_col}), 0) AS gross_pay FROM {table_name} WHERE employee_id = %s AND {year_col} >= 2012 GROUP BY {year_col} ORDER BY {year_col}",
        (PAUL_EMP_ID,),
    )
    return {'columns': sorted(cols), 'rows': [dict(r) for r in rows]}


def summarize_employee_pay_entries(cur):
    table = 'employee_pay_entries'
    if not table_exists(cur, table):
        return None
    cols = set(get_columns(cur, table))
    if 'employee_id' not in cols:
        return {'columns': sorted(cols), 'rows': []}
    date_col = 'pay_date' if 'pay_date' in cols else None
    amount_col = 'gross_amount' if 'gross_amount' in cols else ('gross_pay' if 'gross_pay' in cols else None)
    if not date_col or not amount_col:
        return {'columns': sorted(cols), 'rows': []}
    rows = fetch_all(
        cur,
        f"SELECT EXTRACT(YEAR FROM {date_col})::int AS year, COUNT(*) AS row_count, COALESCE(SUM({amount_col}), 0) AS gross_pay FROM {table} WHERE employee_id = %s AND EXTRACT(YEAR FROM {date_col}) >= 2012 GROUP BY EXTRACT(YEAR FROM {date_col}) ORDER BY EXTRACT(YEAR FROM {date_col})",
        (PAUL_EMP_ID,),
    )
    return {'columns': sorted(cols), 'rows': [dict(r) for r in rows]}


def summarize_gl(cur):
    if not table_exists(cur, 'general_ledger'):
        return None
    cols = set(get_columns(cur, 'general_ledger'))
    if 'entry_date' not in cols:
        return {'columns': sorted(cols), 'rows': []}
    debit_col = 'debit_amount' if 'debit_amount' in cols else ('debit' if 'debit' in cols else None)
    credit_col = 'credit_amount' if 'credit_amount' in cols else ('credit' if 'credit' in cols else None)
    desc_col = 'description' if 'description' in cols else None
    gl_col = 'gl_code' if 'gl_code' in cols else ('account_code' if 'account_code' in cols else None)
    vendor_col = 'vendor_name' if 'vendor_name' in cols else None
    if not (debit_col and credit_col):
        return {'columns': sorted(cols), 'rows': []}
    text_filters = []
    params = []
    if desc_col:
        text_filters.append(f"COALESCE({desc_col}, '') ILIKE %s")
        params.append('%paul%')
        text_filters.append(f"COALESCE({desc_col}, '') ILIKE %s")
        params.append('%karen%')
        text_filters.append(f"COALESCE({desc_col}, '') ILIKE %s")
        params.append('%owner%')
        text_filters.append(f"COALESCE({desc_col}, '') ILIKE %s")
        params.append('%scotia%')
        text_filters.append(f"COALESCE({desc_col}, '') ILIKE %s")
        params.append('%cibc%')
    if vendor_col:
        text_filters.append(f"COALESCE({vendor_col}, '') ILIKE %s")
        params.append('%paul%')
        text_filters.append(f"COALESCE({vendor_col}, '') ILIKE %s")
        params.append('%karen%')
    if gl_col:
        text_filters.append(f"COALESCE({gl_col}::text, '') ILIKE %s")
        params.append('%3020%')
        text_filters.append(f"COALESCE({gl_col}::text, '') ILIKE %s")
        params.append('%5880%')
        text_filters.append(f"COALESCE({gl_col}::text, '') ILIKE %s")
        params.append('%2910%')
        text_filters.append(f"COALESCE({gl_col}::text, '') ILIKE %s")
        params.append('%2550%')
        text_filters.append(f"COALESCE({gl_col}::text, '') ILIKE %s")
        params.append('%2560%')
    if not text_filters:
        return {'columns': sorted(cols), 'rows': []}
    group_cols = ['EXTRACT(YEAR FROM entry_date)::int AS year']
    if gl_col:
        group_cols.append(f'{gl_col}::text AS gl_code')
    if desc_col:
        group_cols.append(f'LEFT(COALESCE({desc_col}, \'\'), 120) AS description_sample')
    query = f"""
        SELECT
            {', '.join(group_cols)},
            COUNT(*) AS row_count,
            COALESCE(SUM({debit_col}), 0) AS debit_sum,
            COALESCE(SUM({credit_col}), 0) AS credit_sum
        FROM general_ledger
        WHERE EXTRACT(YEAR FROM entry_date) >= 2012
          AND ({' OR '.join(text_filters)})
        GROUP BY {', '.join(str(i + 1) for i in range(len(group_cols)))}
        ORDER BY 1, 2 NULLS FIRST, 3 NULLS FIRST
    """
    rows = fetch_all(cur, query, tuple(params))
    return {'columns': sorted(cols), 'rows': [dict(r) for r in rows]}


def dec_default(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError


with psycopg2.connect(**DB, cursor_factory=RealDictCursor) as conn:
    conn.set_session(readonly=True, autocommit=True)
    with conn.cursor() as cur:
        result = {
            'employee': audit_employee(cur)[0],
            'employee_columns': audit_employee(cur)[1],
            'employee_t4_records': audit_employee_t4_records(cur),
            'employee_t4_summary': audit_employee_t4_summary(cur),
            'employee_pay_master': summarize_employee_pay_master(cur),
            'driver_payroll': summarize_driver_payroll(cur),
            'employee_monthly_compensation': summarize_generic_year_table(cur, 'employee_monthly_compensation', 'year', 'gross_pay'),
            'employee_annual_compensation': summarize_generic_year_table(cur, 'employee_annual_compensation', 'year', 'gross_pay'),
            'employee_pay_entries': summarize_employee_pay_entries(cur),
            'general_ledger_related': summarize_gl(cur),
        }

print(json.dumps(result, indent=2, default=dec_default))
