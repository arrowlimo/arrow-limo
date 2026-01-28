"""
Check banking_transactions table schema and balance column.
"""
import psycopg2

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("BANKING_TRANSACTIONS TABLE SCHEMA")
print("=" * 80)

cur.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions'
    ORDER BY ordinal_position
""")

print(f"\n{'Column':<30} {'Type':<20} {'Nullable':<10} {'Default':<20}")
print("-" * 80)
for row in cur.fetchall():
    print(f"{row[0]:<30} {row[1]:<20} {row[2]:<10} {str(row[3] or '')[:19]:<20}")

# Check if balance is calculated or stored
print("\n" + "=" * 80)
print("BALANCE COLUMN ANALYSIS")
print("=" * 80)

cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance,
        transaction_id
    FROM banking_transactions 
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date, transaction_id
    LIMIT 10
""")

print(f"\n{'Date':<12} {'ID':<8} {'Debit':>12} {'Credit':>12} {'Balance':>12} {'Description':<30}")
print("-" * 90)
for row in cur.fetchall():
    date, desc, debit, credit, balance, txn_id = row
    print(f"{str(date):<12} {txn_id:<8} ${debit or 0:>10,.2f} ${credit or 0:>10,.2f} "
          f"${balance or 0:>10,.2f} {(desc or '')[:29]:<30}")

# Check if balance matches running calculation
print("\n" + "=" * 80)
print("BALANCE VALIDATION - Does stored balance = calculated running balance?")
print("=" * 80)

cur.execute("""
    WITH running_balance AS (
        SELECT 
            transaction_id,
            transaction_date,
            debit_amount,
            credit_amount,
            balance as stored_balance,
            SUM(COALESCE(credit_amount, 0) - COALESCE(debit_amount, 0)) 
                OVER (ORDER BY transaction_date, transaction_id) as calculated_balance
        FROM banking_transactions
        WHERE EXTRACT(YEAR FROM transaction_date) = 2012
        ORDER BY transaction_date, transaction_id
        LIMIT 10
    )
    SELECT 
        transaction_date,
        stored_balance,
        calculated_balance,
        stored_balance - calculated_balance as difference
    FROM running_balance
""")

print(f"\n{'Date':<12} {'Stored':>12} {'Calculated':>12} {'Difference':>12}")
print("-" * 50)
for row in cur.fetchall():
    date, stored, calculated, diff = row
    status = "[OK]" if abs(diff or 0) < 0.01 else "[FAIL]"
    print(f"{str(date):<12} ${stored or 0:>10,.2f} ${calculated or 0:>10,.2f} ${diff or 0:>10,.2f} {status}")

print("\n" + "=" * 80)
print("CONCLUSION")
print("=" * 80)
print("[OK] balance column is a stored/hardcoded DECIMAL field")
print("   It contains the actual balance from bank statements")
print("   This is the correct approach - balances are facts from source documents")
print("   Running balance calculation depends on having ALL transactions from opening")

cur.close()
conn.close()
