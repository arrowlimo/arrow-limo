"""
Drop Empty Columns from Receipts Table
CAUTION: This script will PERMANENTLY remove columns with 0% data
Run optimize_schema_analysis.py first to verify which columns are safe to drop
"""
import psycopg2
import os
import sys

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

# List of columns with 0% data that can be safely dropped
EMPTY_COLUMNS = [
    'event_batch_id',
    'reviewed',
    'exported',
    'date_added',
    'tax',
    'tip',
    'type',
    'classification',
    'pay_account',
    'mapped_expense_account_id',
    'mapping_status',
    'mapping_notes',
    'reimbursed_via',
    'reimbursement_date',
    'cash_box_transaction_id',
    'parent_receipt_id',
    'amount_usd',
    'fx_rate',
    'due_date',
    'period_start',
    'period_end',
    'verified_by_user'
]

def confirm_action():
    """Ask user to confirm before making changes."""
    print("⚠️  WARNING ⚠️")
    print(f"This will PERMANENTLY DROP {len(EMPTY_COLUMNS)} columns from the receipts table:")
    print()
    for col in EMPTY_COLUMNS:
        print(f"  • {col}")
    print()
    response = input("Are you absolutely sure? Type 'YES' to proceed: ").strip()
    return response.upper() == "YES"

if not confirm_action():
    print("❌ Cancelled. No changes made.")
    sys.exit(0)

# Create backup first
print()
print("Creating backup before dropping columns...")
os.system("pg_dump -h localhost -U postgres -d almsdata -F c -f almsdata_backup_BEFORE_DROP_EMPTY_COLS.dump")

# Connect and drop columns
conn = psycopg2.connect(
    host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD
)
cur = conn.cursor()

try:
    print()
    print("Dropping empty columns...")
    
    for col in EMPTY_COLUMNS:
        try:
            # Check if column exists
            cur.execute(f"""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'receipts' AND column_name = '{col}'
            """)
            if cur.fetchone():
                print(f"  ✓ Dropping {col}...", end="", flush=True)
                cur.execute(f"ALTER TABLE receipts DROP COLUMN {col} CASCADE")
                print(" done")
            else:
                print(f"  ⊘ {col} not found (already dropped?)")
        except psycopg2.Error as e:
            print(f"  ✗ Error dropping {col}: {e}")
    
    conn.commit()
    print()
    print(f"✅ Successfully dropped {len(EMPTY_COLUMNS)} empty columns")
    print("Database backup saved to: almsdata_backup_BEFORE_DROP_EMPTY_COLS.dump")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    print("Transaction rolled back. No changes made.")

finally:
    cur.close()
    conn.close()
