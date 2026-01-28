import psycopg2

DB = dict(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')

CANDIDATES = [
    ('payments', 'reserve_number'),
    ('payments', 'charter_id'),
    ('payments', 'banking_transaction_id'),
    ('receipts', 'reserve_number'),
    ('receipts', 'charter_id'),
    ('receipts', 'banking_transaction_id'),
    ('receipts', 'vehicle_id'),
    ('receipts', 'employee_id'),
    ('charter_charges', 'reserve_number'),
    ('charter_charges', 'charter_id'),
    ('charter_payments', 'payment_id'),
    ('charter_payments', 'charter_id'),
]

SQL = """
SELECT tc.constraint_name, ccu.table_name AS target_table, ccu.column_name AS target_column
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema = tc.table_schema
WHERE tc.table_schema = 'public'
  AND tc.constraint_type = 'FOREIGN KEY'
  AND kcu.table_name = %s
  AND kcu.column_name = %s
"""


def fetch_fks(cur, table, column):
    cur.execute(SQL, (table, column))
    return cur.fetchall()


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    for table, col in CANDIDATES:
        fks = fetch_fks(cur, table, col)
        status = 'FK' if fks else 'NO FK'
        print(f"{table}.{col}: {status}")
        for name, tgt_table, tgt_col in fks:
            print(f"  -> {name} -> {tgt_table}.{tgt_col}")
    conn.close()


if __name__ == '__main__':
    main()
