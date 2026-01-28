"""
Add driver reimbursement and charter linking columns to receipts table
"""
import psycopg2
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED***')

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 100)
print("ADDING COLUMNS TO RECEIPTS TABLE FOR DRIVER REIMBURSEMENT AND CHARTER LINKING")
print("=" * 100)

try:
    # Check if employee_id column already exists
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'receipts' AND column_name = 'employee_id'
    """)
    if not cur.fetchone():
        print("\n✓ Adding employee_id column...")
        cur.execute("""
            ALTER TABLE receipts
            ADD COLUMN employee_id INTEGER REFERENCES employees(employee_id)
        """)
        print("  ✓ employee_id column added")
    else:
        print("\n✓ employee_id column already exists")

    # Check if charter_id column already exists
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'receipts' AND column_name = 'charter_id'
    """)
    if not cur.fetchone():
        print("\n✓ Adding charter_id column...")
        cur.execute("""
            ALTER TABLE receipts
            ADD COLUMN charter_id INTEGER REFERENCES charters(charter_id)
        """)
        print("  ✓ charter_id column added")
    else:
        print("\n✓ charter_id column already exists")

    # Check if reserve_number column already exists
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'receipts' AND column_name = 'reserve_number'
    """)
    if not cur.fetchone():
        print("\n✓ Adding reserve_number column...")
        cur.execute("""
            ALTER TABLE receipts
            ADD COLUMN reserve_number VARCHAR(20)
        """)
        print("  ✓ reserve_number column added")
    else:
        print("\n✓ reserve_number column already exists")

    conn.commit()
    print("\n" + "=" * 100)
    print("✅ All columns added successfully!")
    print("=" * 100)

except Exception as e:
    conn.rollback()
    print(f"\n❌ Error: {e}")
    raise

finally:
    cur.close()
    conn.close()
