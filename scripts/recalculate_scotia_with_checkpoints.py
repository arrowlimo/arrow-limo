import psycopg2
from decimal import Decimal
import sys
from datetime import date

# Add --write flag to actually apply changes
DRY_RUN = '--write' not in sys.argv

# Month-end checkpoint balances from user
CHECKPOINTS = {
    date(2012, 1, 31): Decimal('-136.02'),
    date(2012, 2, 29): Decimal('91.00'),
    date(2012, 3, 31): Decimal('91.00'),
    date(2012, 4, 30): Decimal('266.00'),
    date(2012, 5, 31): Decimal('1069.27'),
    date(2012, 6, 30): Decimal('4195.89'),
    date(2012, 7, 31): Decimal('8000.21'),
    date(2012, 8, 31): Decimal('591.06'),
    date(2012, 9, 30): Decimal('3122.29'),
    date(2012, 10, 31): Decimal('430.21'),
    date(2012, 11, 30): Decimal('5.23'),
    date(2012, 12, 31): Decimal('952.04'),
    date(2013, 1, 31): Decimal('-136.02'),
    date(2013, 2, 28): Decimal('-245.38'),
    date(2013, 3, 28): Decimal('613.92'),
    date(2013, 4, 30): Decimal('3753.36'),
    date(2013, 5, 31): Decimal('374.92'),
    date(2013, 6, 28): Decimal('6731.59'),
    date(2013, 7, 31): Decimal('3935.58'),
    date(2013, 8, 30): Decimal('2112.22'),
    date(2013, 9, 30): Decimal('-384.42'),
    date(2013, 10, 31): Decimal('4228.16'),
    date(2013, 11, 29): Decimal('-4480.57'),
    date(2013, 12, 31): Decimal('6404.87'),
}

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost"
)
cur = conn.cursor()

print("=" * 80)
if DRY_RUN:
    print("DRY RUN - Scotia 2012-2013 Balance Recalculation with Checkpoints")
    print("Add --write flag to apply changes")
else:
    print("LIVE RUN - Scotia 2012-2013 Balance Recalculation with Checkpoints")
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
print(f"Month-end checkpoints loaded: {len(CHECKPOINTS)}")

# Process transactions month by month, using checkpoints
updates = []
balance_changes = []
checkpoint_results = []

# Group transactions by year-month
from collections import defaultdict
months = defaultdict(list)

for txn in transactions:
    txn_id, txn_date, desc, debit, credit, old_balance = txn
    year_month = (txn_date.year, txn_date.month)
    months[year_month].append(txn)

# Process each month
for year_month in sorted(months.keys()):
    year, month = year_month
    month_txns = months[year_month]
    
    print(f"\nProcessing {year}-{month:02d}: {len(month_txns)} transactions")
    
    # Find the checkpoint for this month (last day of month)
    # Get last transaction date of the month
    last_txn_date = max(t[1] for t in month_txns)
    
    # Find checkpoint that applies to this month
    checkpoint_date = None
    checkpoint_balance = None
    for cp_date, cp_bal in CHECKPOINTS.items():
        if cp_date.year == year and cp_date.month == month:
            checkpoint_date = cp_date
            checkpoint_balance = cp_bal
            break
    
    if checkpoint_balance is None:
        print(f"  WARNING: No checkpoint found for {year}-{month:02d}")
        continue
    
    # Calculate what the starting balance should be for this month
    # Sum all debits and credits for the month
    month_debits = sum(Decimal(str(t[3])) if t[3] else Decimal('0') for t in month_txns)
    month_credits = sum(Decimal(str(t[4])) if t[4] else Decimal('0') for t in month_txns)
    net_change = month_credits - month_debits
    
    # Starting balance = ending balance - net change
    starting_balance = checkpoint_balance - net_change
    
    print(f"  Checkpoint: {checkpoint_date} = ${float(checkpoint_balance):,.2f}")
    print(f"  Net change: ${float(net_change):,.2f} (Credits: ${float(month_credits):,.2f}, Debits: ${float(month_debits):,.2f})")
    print(f"  Calculated starting balance: ${float(starting_balance):,.2f}")
    
    # Now recalculate running balance for each transaction in the month
    running_balance = starting_balance
    
    for txn_id, txn_date, desc, debit, credit, old_balance in month_txns:
        debit = Decimal(str(debit)) if debit else Decimal('0')
        credit = Decimal(str(credit)) if credit else Decimal('0')
        old_balance = Decimal(str(old_balance)) if old_balance else Decimal('0')
        
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
    
    # Verify ending balance matches checkpoint
    if abs(running_balance - checkpoint_balance) > Decimal('0.01'):
        print(f"  ✗ ERROR: Ending balance ${float(running_balance):,.2f} does not match checkpoint ${float(checkpoint_balance):,.2f}")
        print(f"    Difference: ${float(running_balance - checkpoint_balance):,.2f}")
    else:
        print(f"  ✓ Ending balance matches checkpoint: ${float(running_balance):,.2f}")
    
    checkpoint_results.append({
        'date': checkpoint_date,
        'expected': checkpoint_balance,
        'calculated': running_balance,
        'match': abs(running_balance - checkpoint_balance) < Decimal('0.01')
    })

print(f"\nBalance changes detected: {len(balance_changes):,} out of {len(transactions):,} transactions")
print(f"Checkpoints verified: {len(checkpoint_results)}")

# Show checkpoint verification
print("\n" + "=" * 80)
print("MONTH-END CHECKPOINT VERIFICATION:")
print("-" * 80)
all_match = True
for cp in checkpoint_results:
    match = "✓" if cp['match'] else "✗"
    if not cp['match']:
        all_match = False
    print(f"{match} {cp['date']} | Expected: ${float(cp['expected']):>12,.2f} | Calculated: ${float(cp['calculated']):>12,.2f}")

if all_match:
    print("\n✓ All checkpoints match!")
else:
    print("\n✗ Some checkpoints do not match - review calculations above")

# Show sample of balance changes
if balance_changes:
    print("\n" + "=" * 80)
    print("SAMPLE BALANCE CHANGES (First 10):")
    print("-" * 80)
    for change in balance_changes[:10]:
        print(f"{change['date']} | {change['desc']:<30} | Old: ${float(change['old_balance']):>12,.2f} | New: ${float(change['new_balance']):>12,.2f}")

# Apply updates if --write flag provided
if not DRY_RUN:
    print("\n" + "=" * 80)
    print("APPLYING UPDATES TO DATABASE...")
    print("-" * 80)
    
    # Create backup first
    timestamp = date.today().strftime('%Y%m%d')
    backup_table = f"banking_transactions_scotia_2012_2013_backup_{timestamp}"
    
    cur.execute(f"""
        DROP TABLE IF EXISTS {backup_table}
    """)
    
    cur.execute(f"""
        CREATE TABLE {backup_table} AS
        SELECT * FROM banking_transactions
        WHERE account_number = '903990106011'
        AND EXTRACT(YEAR FROM transaction_date) IN (2012, 2013)
    """)
    
    print(f"✓ Backup created: {backup_table}")
    
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
    
    # Verify final balances
    print("\n" + "=" * 80)
    print("VERIFICATION - Final balances after update:")
    print("-" * 80)
    
    for check_date in [date(2012, 12, 31), date(2013, 12, 31)]:
        cur.execute("""
            SELECT balance FROM banking_transactions
            WHERE account_number = '903990106011'
            AND transaction_date = %s
            ORDER BY transaction_id DESC
            LIMIT 1
        """, (check_date,))
        result = cur.fetchone()
        if result:
            actual = float(result[0])
            expected = float(CHECKPOINTS.get(check_date, 0))
            match = "✓" if abs(actual - expected) < 0.01 else "✗"
            print(f"{match} {check_date}: ${actual:,.2f} (expected ${expected:,.2f})")
else:
    print("\n" + "=" * 80)
    print("DRY RUN COMPLETE - No changes made")
    print("Run with --write flag to apply updates")

cur.close()
conn.close()
