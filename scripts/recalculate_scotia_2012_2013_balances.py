import psycopg2
from decimal import Decimal
import sys

# Add --write flag to actually apply changes
DRY_RUN = '--write' not in sys.argv

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REMOVED***",
    host="localhost"
)
cur = conn.cursor()

print("=" * 80)
if DRY_RUN:
    print("DRY RUN - Scotia 2012-2013 Balance Recalculation")
    print("Add --write flag to apply changes")
else:
    print("LIVE RUN - Scotia 2012-2013 Balance Recalculation")
print("=" * 80)

# Get all 2012-2013 transactions in chronological order
cur.execute("""
    SELECT transaction_id, transaction_date, description, debit_amount, credit_amount, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) IN (2012, 2013)
    ORDER BY transaction_date ASC, transaction_id ASC
""")

transactions = cur.fetchall()
print(f"\nTotal transactions to recalculate: {len(transactions):,}")

# Starting balance for 2012
running_balance = Decimal('40.00')
print(f"Starting balance (Jan 1, 2012): ${running_balance}")

updates = []
balance_changes = []

for txn_id, txn_date, desc, debit, credit, old_balance in transactions:
    # Convert to Decimal for precision
    debit = Decimal(str(debit)) if debit else Decimal('0')
    credit = Decimal(str(credit)) if credit else Decimal('0')
    old_balance = Decimal(str(old_balance)) if old_balance else Decimal('0')
    
    # Calculate new running balance
    running_balance = running_balance + credit - debit
    
    # Track if balance changed
    if abs(running_balance - old_balance) > Decimal('0.01'):
        balance_changes.append({
            'txn_id': txn_id,
            'date': txn_date,
            'desc': desc,
            'old_balance': old_balance,
            'new_balance': running_balance,
            'difference': running_balance - old_balance
        })
    
    updates.append((running_balance, txn_id))

print(f"\nBalance changes detected: {len(balance_changes):,} out of {len(transactions):,} transactions")

# Show sample of balance changes
if balance_changes:
    print("\nFIRST 10 BALANCE CHANGES:")
    print("-" * 80)
    for change in balance_changes[:10]:
        print(f"{change['date']} | {change['desc']:<30} | Old: ${float(change['old_balance']):>12,.2f} | New: ${float(change['new_balance']):>12,.2f} | Diff: ${float(change['difference']):>12,.2f}")
    
    if len(balance_changes) > 10:
        print(f"\n... ({len(balance_changes) - 10:,} more changes)")
    
    print("\nLAST 10 BALANCE CHANGES:")
    print("-" * 80)
    for change in balance_changes[-10:]:
        print(f"{change['date']} | {change['desc']:<30} | Old: ${float(change['old_balance']):>12,.2f} | New: ${float(change['new_balance']):>12,.2f} | Diff: ${float(change['difference']):>12,.2f}")

# Show final balances
print("\n" + "=" * 80)
print("FINAL BALANCES:")
print("-" * 80)

# Find 2012 ending
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
""")
last_2012 = cur.fetchone()
if last_2012:
    print(f"2012 Ending (current):  ${float(last_2012[2]):,.2f} on {last_2012[0]}")

# Find 2013 ending
cur.execute("""
    SELECT transaction_date, description, balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    AND EXTRACT(YEAR FROM transaction_date) = 2013
    ORDER BY transaction_date DESC, transaction_id DESC
    LIMIT 1
""")
last_2013 = cur.fetchone()
if last_2013:
    print(f"2013 Ending (current):  ${float(last_2013[2]):,.2f} on {last_2013[0]}")

# Get recalculated ending balances
if updates:
    # Find last 2012 transaction
    for txn_id, txn_date, desc, debit, credit, old_balance in transactions:
        if txn_date.year == 2012:
            last_2012_recalc = running_balance
    
    # Get final balance from updates (last one)
    final_balance = updates[-1][0]
    
    print(f"\n2012 Ending (recalculated): ${float(last_2012_recalc):,.2f}")
    print(f"Expected: $952.04")
    if abs(float(last_2012_recalc) - 952.04) < 0.01:
        print("✓ 2012 MATCHES expected")
    else:
        print(f"✗ 2012 difference: ${float(last_2012_recalc) - 952.04:,.2f}")
    
    print(f"\n2013 Ending (recalculated): ${float(final_balance):,.2f}")
    print(f"Expected: $6,404.87")
    if abs(float(final_balance) - 6404.87) < 0.01:
        print("✓ 2013 MATCHES expected")
    else:
        print(f"✗ 2013 difference: ${float(final_balance) - 6404.87:,.2f}")

# Apply updates if --write flag provided
if not DRY_RUN:
    print("\n" + "=" * 80)
    print("APPLYING UPDATES TO DATABASE...")
    print("-" * 80)
    
    # Create backup first
    cur.execute("""
        CREATE TABLE IF NOT EXISTS banking_transactions_scotia_2012_2013_backup AS
        SELECT * FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) IN (2012, 2013)
    """)
    
    backup_count = cur.rowcount
    print(f"Backup created: banking_transactions_scotia_2012_2013_backup ({backup_count:,} rows)")
    
    # Update balances
    update_count = 0
    for new_balance, txn_id in updates:
        cur.execute("""
            UPDATE banking_transactions
            SET balance = %s
            WHERE transaction_id = %s
        """, (new_balance, txn_id))
        update_count += cur.rowcount
    
    conn.commit()
    print(f"✓ Updated {update_count:,} transaction balances")
    print("✓ Changes committed to database")
else:
    print("\n" + "=" * 80)
    print("DRY RUN COMPLETE - No changes made")
    print("Run with --write flag to apply updates")

cur.close()
conn.close()
