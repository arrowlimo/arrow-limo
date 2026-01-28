import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REMOVED***"
)

cur = conn.cursor()

columns_to_add = [
    ('transaction_date', 'DATE'),
    ('distribution_account_number', 'TEXT'),
    ('account_full_name', 'TEXT'),
    ('supplier', 'TEXT'),
    ('item_supplier_company', 'TEXT'),
    ('account_number', 'TEXT'),
    ('tax_slip_type', 'TEXT'),
    ('account_name', 'TEXT'),
    ('account_type', 'TEXT'),
    ('account_description', 'TEXT'),
    ('parent_account_id', 'TEXT'),
    ('customer', 'TEXT'),
    ('customer_full_name', 'TEXT'),
    ('customer_title', 'TEXT'),
    ('customer_first_name', 'TEXT'),
    ('customer_middle_name', 'TEXT'),
    ('employee', 'TEXT'),
    ('employee_deleted', 'TEXT'),
    ('employee_billing_rate', 'NUMERIC'),
    ('employee_id', 'TEXT'),
    ('employee_billable', 'TEXT'),
    ('po_number', 'TEXT'),
    ('ungrouped_tags', 'TEXT'),
    ('transaction_id', 'TEXT'),
    ('tax_code', 'TEXT'),
    ('tax_name', 'TEXT'),
    ('distribution_account', 'TEXT'),
    ('distribution_account_type', 'TEXT'),
    ('distribution_account_description', 'TEXT'),
    ('parent_distribution_account_id', 'TEXT'),
    ('distribution_account_subtype', 'TEXT'),
    ('parent_distribution_account', 'TEXT'),
    ('distribution_account_is_sub_account', 'TEXT')
]

print("Adding columns to general_ledger table...")

for col_name, col_type in columns_to_add:
    try:
        sql = f"ALTER TABLE general_ledger ADD COLUMN {col_name} {col_type};"
        cur.execute(sql)
        conn.commit()
        print(f"✓ Added column: {col_name} ({col_type})")
    except psycopg2.errors.DuplicateColumn:
        conn.rollback()
        print(f"- Column already exists: {col_name}")
    except Exception as e:
        conn.rollback()
        print(f"✗ Error adding {col_name}: {e}")

cur.close()
conn.close()

print("\nSchema update complete!")
