import os
import psycopg2
from decimal import Decimal

DB = dict(
    host=os.getenv('DB_HOST','localhost'),
    database=os.getenv('DB_NAME','almsdata'),
    user=os.getenv('DB_USER','postgres'),
    password=os.getenv('DB_PASSWORD','***REDACTED***'),
)

CANDIDATE_TABLES = [
    'chauffeur_pay_entries',
    'driver_pay_entries',
    'employee_pay_entries',
]

DATE_COLUMNS = ['pay_date', 'txn_date', 'date', 'paid_at', 'created_at']
YEAR_COLS = ['year']
MONTH_COLS = ['month']
AMOUNT_COLUMNS = ['gross_pay','gross','amount','net_amount','wage','pay','total','earnings','total_pay']


def get_conn():
    return psycopg2.connect(**DB)


def get_cols(cur, table):
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name=%s
    """, (table,))
    return {r[0]: r[1] for r in cur.fetchall()}


def try_sum(cur, table):
    cols = get_cols(cur, table)
    if not cols:
        return (table, 'missing', None)

    # Determine date predicate for August 2012
    predicate = None
    if 'year' in cols and 'month' in cols:
        predicate = "year=2012 AND month=8"
    else:
        dt_col = next((c for c in DATE_COLUMNS if c in cols), None)
        if dt_col:
            predicate = f"{dt_col} >= '2012-08-01' AND {dt_col} < '2012-09-01'"

    # Choose an amount column
    amt_col = next((c for c in AMOUNT_COLUMNS if c in cols), None)

    if not predicate or not amt_col:
        return (table, 'no_usable_columns', {'columns': cols, 'predicate': predicate, 'amount_try': amt_col})

    try:
        cur.execute(f"SELECT COALESCE(SUM({amt_col}),0) FROM {table} WHERE {predicate}")
        total = cur.fetchone()[0]
        return (table, 'ok', {'amount_column': amt_col, 'sum': Decimal(total)})
    except Exception as e:
        return (table, 'error', {'error': str(e), 'columns': cols})


def main():
    conn = get_conn(); cur = conn.cursor()
    for t in CANDIDATE_TABLES:
        cur.execute("""SELECT EXISTS (
            SELECT FROM information_schema.tables WHERE table_name=%s
        )""", (t,))
        exists = cur.fetchone()[0]
        if not exists:
            print(f"{t}: table not found")
            continue
        table, status, info = try_sum(cur, t)
        if status == 'ok':
            print(f"{table}: sum({info['amount_column']}) for Aug 2012 = {info['sum']:.2f}")
        elif status == 'no_usable_columns':
            print(f"{table}: no usable date/amount columns; columns={list(info['columns'].keys())}")
        elif status == 'error':
            print(f"{table}: error {info['error']}; columns={list(info['columns'].keys())}")
        else:
            print(f"{table}: status={status}")
    conn.close()

if __name__ == '__main__':
    main()
