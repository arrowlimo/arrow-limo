import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

# Check if charter_id column exists on receipts
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'receipts' AND column_name LIKE '%charter%'
""")
charter_cols = cur.fetchall()

if charter_cols:
    print("Charter columns found on receipts:")
    for col in charter_cols:
        print(f"  ✓ {col[0]}")
else:
    print("No charter columns on receipts table - need to add!")
    print("\nRecommended additions:")
    print("  ALTER TABLE receipts ADD COLUMN charter_id INTEGER REFERENCES charters(charter_id);")
    print("  ALTER TABLE receipts ADD COLUMN reserve_number VARCHAR(20);")

# Check if employee_id column exists for tracking reimbursement recipient
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'receipts' AND column_name = 'employee_id'
""")
emp_col = cur.fetchone()

if emp_col:
    print("\nEmployee ID column found on receipts: ✓")
else:
    print("\nEmployee ID column NOT found on receipts - need to add!")
    print("  ALTER TABLE receipts ADD COLUMN employee_id INTEGER REFERENCES employees(employee_id);")

# List the reimbursement columns
print("\nExisting reimbursement columns on receipts:")
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'receipts' AND column_name LIKE '%reimburs%'
    ORDER BY ordinal_position
""")
for col_name, data_type in cur.fetchall():
    print(f"  {col_name:40s} | {data_type}")

conn.close()
