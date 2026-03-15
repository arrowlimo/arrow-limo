"""
Check and add Jan 1 opening balance if missing.
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 80)
print("JANUARY 1 OPENING BALANCE CHECK")
print("=" * 80)

# Check for Jan 1 transaction
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date = '2012-01-01'
    ORDER BY transaction_id
""")

jan1_txns = cur.fetchall()

if jan1_txns:
    print(f"\n[OK] Found {len(jan1_txns)} transaction(s) on Jan 1, 2012:")
    for txn in jan1_txns:
        print(f"  Date: {txn[0]}")
        print(f"  Description: {txn[1]}")
        print(f"  Balance: ${txn[2]:,.2f}")
else:
    print("\n[WARN] No transactions found on Jan 1, 2012")
    print("\nExpected Jan 1 opening balance: $7,177.34")
    print("\nWould you like to add it? Run with --write flag")

# Check first transaction in database
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE transaction_date >= '2012-01-01' AND transaction_date <= '2012-01-31'
    ORDER BY transaction_date, transaction_id
    LIMIT 1
""")

first_txn = cur.fetchone()
print(f"\n{'='*80}")
print("FIRST JANUARY TRANSACTION IN DATABASE")
print("=" * 80)
print(f"\nDate: {first_txn[0]}")
print(f"Description: {first_txn[1]}")
print(f"Balance: ${first_txn[2]:,.2f}")

# Check if we need to add opening balance
import sys
if '--write' in sys.argv and not jan1_txns:
    print(f"\n{'='*80}")
    print("ADDING JAN 1 OPENING BALANCE")
    print("=" * 80)
    
    # Create backup
    backup_name = f"banking_transactions_jan1_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\nCreating backup: {backup_name}")
    cur.execute(f"""
        CREATE TABLE {backup_name} AS 
        SELECT * FROM banking_transactions 
        WHERE transaction_date = '2012-01-01'
    """)
    conn.commit()
    
    # Insert opening balance
    print("\nInserting Jan 1 opening balance: $7,177.34")
    cur.execute("""
        INSERT INTO banking_transactions 
        (transaction_date, description, debit_amount, credit_amount, balance, account_number)
        VALUES ('2012-01-01', 'Opening balance', NULL, NULL, 7177.34, '0228362')
    """)
    conn.commit()
    print("[OK] Opening balance added")
    
    # Verify
    cur.execute("""
        SELECT transaction_date, description, balance
        FROM banking_transactions
        WHERE transaction_date = '2012-01-01'
    """)
    result = cur.fetchone()
    print(f"\nVerification:")
    print(f"  Date: {result[0]}")
    print(f"  Description: {result[1]}")
    print(f"  Balance: ${result[2]:,.2f}")

cur.close()
conn.close()
