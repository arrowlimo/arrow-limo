import os
import psycopg2

TARGETS = {
    'clients': ['billing_address', 'contact_info', 'square_customer_id', 'warning_flag'],
    'vehicles': ['vehicle_type', 'unit_number', 'current_mileage', 'status'],
    'receipts': ['receipt_id'],
    'banking_transactions': ['receipt_id'],
    'employees': ['termination_date']
}

TABLE_RENAMES = [
    ('staging_driver_pay', 'staging_qb_accounts'),
]

def get_conn():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***'),
    )


def table_exists(cur, name):
    cur.execute("""
        SELECT EXISTS(
            SELECT 1 FROM information_schema.tables
            WHERE table_schema='public' AND table_name=%s
        )
    """, (name,))
    return cur.fetchone()[0]


def get_columns(cur, table):
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
    """, (table,))
    return {r[0] for r in cur.fetchall()}


def main():
    conn = get_conn()
    cur = conn.cursor()

    print("Table rename checks:")
    for old, new in TABLE_RENAMES:
        print(f"- {old} -> {new}: ", end='')
        has_old = table_exists(cur, old)
        has_new = table_exists(cur, new)
        if not has_old and has_new:
            print("✓ renamed")
        elif has_old and not has_new:
            print("✗ still old name present")
        else:
            print(f"info (old_exists={has_old}, new_exists={has_new})")

    print("\nColumn presence checks:")
    for table, cols in TARGETS.items():
        existing = get_columns(cur, table)
        missing = [c for c in cols if c not in existing]
        if not missing:
            print(f"- {table}: ✓ {len(cols)}/ {len(cols)} present")
        else:
            print(f"- {table}: missing {missing}")
            if table == 'clients':
                print(f"  existing columns: {sorted(existing)}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
