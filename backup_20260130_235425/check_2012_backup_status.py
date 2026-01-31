import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api import get_db_connection

conn = get_db_connection()
cur = conn.cursor()

print("\n=== CHECKING 2012 BACKUP HISTORY ===\n")

# Check for backup tables
cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    AND (
        table_name LIKE '%2012%backup%' 
        OR table_name LIKE '%backup%2012%'
        OR table_name LIKE 'scotia_2012%'
        OR table_name LIKE 'banking_transactions_2012%'
    )
    ORDER BY table_name
""")
backup_tables = cur.fetchall()

print("2012 Banking Backup Tables Found:")
for table in backup_tables:
    cur.execute(f"SELECT COUNT(*) FROM {table[0]}")
    count = cur.fetchone()[0]
    print(f"  - {table[0]}: {count} rows")

print(f"\nTotal backup tables: {len(backup_tables)}")

# Check current 2012 data
print("\n=== CURRENT 2012 DATA IN banking_transactions ===\n")

cur.execute("""
    SELECT 
        account_number,
        COUNT(*) as txn_count,
        MIN(transaction_date) as first_date,
        MAX(transaction_date) as last_date,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    GROUP BY account_number
    ORDER BY account_number
""")

for row in cur.fetchall():
    print(f"Account: {row[0]}")
    print(f"  Transactions: {row[1]}")
    print(f"  Date Range: {row[2]} to {row[3]}")
    print(f"  Debits: ${row[4]:,.2f}")
    print(f"  Credits: ${row[5]:,.2f}\n")

conn.close()
