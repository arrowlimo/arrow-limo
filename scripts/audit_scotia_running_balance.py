"""
Audit Scotia Bank 903990106011 running balance from beginning.
Calculate expected balance after each transaction and flag discrepancies.
"""

import psycopg2
from decimal import Decimal

def get_db_connection():
    return psycopg2.connect(
        host='localhost',
        database='almsdata',
        user='postgres',
        password='***REMOVED***'
    )

conn = get_db_connection()
cur = conn.cursor()

print("SCOTIA BANK RUNNING BALANCE AUDIT")
print("="*80)
print("Account: 903990106011")
print()

# Get all transactions in chronological order
cur.execute("""
    SELECT 
        transaction_id,
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE account_number = '903990106011'
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"Total transactions: {len(transactions)}")
print()

# Find the first transaction with a balance
opening_balance = None
for txn in transactions:
    if txn[5] is not None:
        opening_balance = Decimal(str(txn[5]))
        # If this is not a balance forward, calculate backwards
        if txn[3]:  # Has debit
            opening_balance += Decimal(str(txn[3]))
        elif txn[4]:  # Has credit
            opening_balance -= Decimal(str(txn[4]))
        break

if opening_balance is None:
    # No balance found, start at 0
    opening_balance = Decimal('0.00')
    print("WARNING: No opening balance found, starting at $0.00")
else:
    print(f"Opening balance (calculated): ${opening_balance:.2f}")

print()
print("Auditing transactions...")
print("-"*80)

running_balance = opening_balance
issues = []
balance_mismatches = []
null_balances = []

for i, txn in enumerate(transactions, 1):
    txn_id, date, desc, debit, credit, recorded_balance = txn
    
    # Calculate expected balance
    if debit:
        running_balance -= Decimal(str(debit))
    if credit:
        running_balance += Decimal(str(credit))
    
    # Check against recorded balance
    if recorded_balance is not None:
        recorded = Decimal(str(recorded_balance))
        difference = abs(running_balance - recorded)
        
        if difference > Decimal('0.01'):  # More than 1 cent off
            desc_short = (desc[:40] if desc else "N/A").ljust(40)
            balance_mismatches.append({
                'txn': i,
                'id': txn_id,
                'date': date,
                'desc': desc_short,
                'expected': running_balance,
                'recorded': recorded,
                'diff': difference
            })
            
            print(f"MISMATCH #{len(balance_mismatches)}:")
            print(f"  Txn {i} | ID {txn_id} | {date}")
            print(f"  {desc_short}")
            print(f"  Expected: ${running_balance:>12.2f}")
            print(f"  Recorded: ${recorded:>12.2f}")
            print(f"  Diff:     ${difference:>12.2f}")
            print()
            
            # Reset running balance to recorded to continue audit
            running_balance = recorded
    else:
        null_balances.append({
            'txn': i,
            'id': txn_id,
            'date': date
        })

print("="*80)
print("\nAUDIT SUMMARY:")
print(f"Total transactions audited: {len(transactions)}")
print(f"Opening balance: ${opening_balance:.2f}")
print(f"Final running balance: ${running_balance:.2f}")
print()
print(f"Balance mismatches found: {len(balance_mismatches)}")
print(f"Transactions with NULL balance: {len(null_balances)}")

if balance_mismatches:
    print()
    print("BALANCE MISMATCH DETAILS:")
    print("-"*80)
    for m in balance_mismatches[:20]:  # Show first 20
        print(f"{m['date']} | Txn {m['txn']:>4} | ID {m['id']:>6} | Diff: ${m['diff']:>10.2f}")
    if len(balance_mismatches) > 20:
        print(f"... and {len(balance_mismatches) - 20} more")

if null_balances:
    print()
    print(f"NULL BALANCES: {len(null_balances)} transactions missing balance field")
    print("Date range:", null_balances[0]['date'], "to", null_balances[-1]['date'])

# Check for date gaps
print()
print("Checking for date gaps...")
print("-"*80)
from datetime import timedelta

gaps = []
prev_date = None
for txn in transactions:
    txn_id, date, desc, debit, credit, balance = txn
    if prev_date and date:
        gap_days = (date - prev_date).days
        if gap_days > 7:  # More than 1 week gap
            gaps.append({
                'from': prev_date,
                'to': date,
                'days': gap_days
            })
    prev_date = date

if gaps:
    print(f"Found {len(gaps)} gaps of more than 7 days:")
    for g in gaps[:10]:
        print(f"  {g['from']} → {g['to']} ({g['days']} days)")
else:
    print("No significant date gaps found.")

cur.close()
conn.close()
