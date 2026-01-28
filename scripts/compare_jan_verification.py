"""
Compare database banking_transactions against manual verification report for January 2012.
Parse the markdown verification file and compare line-by-line.
"""
import psycopg2
from datetime import datetime
import re

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("=" * 80)
print("COMPARING DATABASE VS MANUAL VERIFICATION - JANUARY 2012")
print("=" * 80)

# Parse manual verification file
print("\nLoading manual verification data from markdown file...")
manual_txns = []

with open('l:/limo/reports/2012_cibc_complete_running_balance_verification.md', encoding='utf-8') as f:
    content = f.read()
    
    # Extract January section
    jan_section = content.split('## February 2012')[0] if '## February 2012' in content else content
    
    # Parse table rows
    lines = jan_section.split('\n')
    for line in lines:
        if '|' in line and '[OK]' in line:
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 6:
                try:
                    date = parts[1]
                    description = parts[2]
                    txn_type = parts[3]
                    amount = parts[4].replace('$', '').replace(',', '').strip()
                    balance = parts[6].replace('$', '').replace(',', '').strip()
                    
                    if date and date != 'Date' and date != '---' and amount and amount != '-':
                        manual_txns.append({
                            'date': date,
                            'description': description,
                            'type': txn_type,
                            'amount': float(amount),
                            'balance': float(balance)
                        })
                except (ValueError, IndexError):
                    continue

print(f"[OK] Loaded {len(manual_txns)} manually verified transactions")

# Get database transactions for January 2012
print("\nLoading database transactions for January 2012...")
cur.execute("""
    SELECT 
        transaction_date,
        description,
        debit_amount,
        credit_amount,
        balance
    FROM banking_transactions
    WHERE TO_CHAR(transaction_date, 'YYYY-MM') = '2012-01'
    ORDER BY transaction_date, transaction_id
""")

db_txns = []
for date, desc, debit, credit, balance in cur.fetchall():
    db_txns.append({
        'date': str(date),
        'description': desc or '',
        'debit': float(debit or 0),
        'credit': float(credit or 0),
        'balance': float(balance or 0)
    })

print(f"[OK] Loaded {len(db_txns)} database transactions")

# Analysis
print("\n" + "=" * 80)
print("COMPARISON ANALYSIS")
print("=" * 80)

print(f"\nManual verification: {len(manual_txns)} transactions")
print(f"Database: {len(db_txns)} transactions")
print(f"Difference: {len(manual_txns) - len(db_txns)} transactions")

# Compare totals
manual_withdrawals = sum(t['amount'] for t in manual_txns if t['type'] == 'W')
manual_deposits = sum(t['amount'] for t in manual_txns if t['type'] == 'D')
db_withdrawals = sum(t['debit'] for t in db_txns)
db_deposits = sum(t['credit'] for t in db_txns)

print(f"\nWithdrawals: Manual ${manual_withdrawals:,.2f} vs DB ${db_withdrawals:,.2f} (Δ ${manual_withdrawals - db_withdrawals:,.2f})")
print(f"Deposits: Manual ${manual_deposits:,.2f} vs DB ${db_deposits:,.2f} (Δ ${manual_deposits - db_deposits:,.2f})")

# Opening/closing balances
if manual_txns:
    manual_opening = None
    for t in manual_txns:
        if 'opening' in t['description'].lower():
            manual_opening = t['balance']
            break
    manual_closing = manual_txns[-1]['balance']
    
    db_opening = db_txns[0]['balance'] if db_txns else 0
    db_closing = db_txns[-1]['balance'] if db_txns else 0
    
    print(f"\nOpening balance: Manual ${manual_opening or 0:,.2f} vs DB ${db_opening:,.2f}")
    print(f"Closing balance: Manual ${manual_closing:,.2f} vs DB ${db_closing:,.2f}")

# Find transactions in manual but not in database
print("\n" + "=" * 80)
print("TRANSACTIONS IN MANUAL VERIFICATION BUT NOT IN DATABASE")
print("=" * 80)

# Create a simple matching: look for similar amounts and dates
missing_from_db = []
for manual_txn in manual_txns:
    # Skip opening/closing balance entries
    if manual_txn['type'] == '-':
        continue
    
    # Try to find matching transaction in database
    manual_date = manual_txn['date'].replace('Jan ', '2012-01-').replace('Feb ', '2012-02-')
    manual_amount = manual_txn['amount']
    manual_is_withdrawal = (manual_txn['type'] == 'W')
    
    found = False
    for db_txn in db_txns:
        db_date = db_txn['date']
        db_amount = db_txn['debit'] if manual_is_withdrawal else db_txn['credit']
        
        if manual_date in db_date and abs(manual_amount - db_amount) < 0.01:
            found = True
            break
    
    if not found:
        missing_from_db.append(manual_txn)

if missing_from_db:
    print(f"\nFound {len(missing_from_db)} transactions missing from database:")
    print(f"{'Date':<12} {'Type':<6} {'Amount':>12} {'Balance':>12} {'Description':<40}")
    print("-" * 80)
    for t in missing_from_db[:20]:  # Show first 20
        print(f"{t['date']:<12} {t['type']:<6} ${t['amount']:>10,.2f} ${t['balance']:>10,.2f} {t['description'][:39]}")
    
    if len(missing_from_db) > 20:
        print(f"... and {len(missing_from_db) - 20} more")
else:
    print("\n[OK] All manually verified transactions found in database")

# Find transactions in database but not in manual verification
print("\n" + "=" * 80)
print("TRANSACTIONS IN DATABASE BUT NOT IN MANUAL VERIFICATION")
print("=" * 80)

extra_in_db = []
for db_txn in db_txns:
    # Try to find matching in manual verification
    db_date = db_txn['date'][5:10]  # MM-DD
    db_amount = db_txn['debit'] if db_txn['debit'] > 0 else db_txn['credit']
    
    found = False
    for manual_txn in manual_txns:
        if manual_txn['type'] == '-':
            continue
        manual_date = manual_txn['date'].replace('Jan ', '01-').replace('Feb ', '02-')
        manual_amount = manual_txn['amount']
        
        if db_date in manual_date and abs(db_amount - manual_amount) < 0.01:
            found = True
            break
    
    if not found:
        extra_in_db.append(db_txn)

if extra_in_db:
    print(f"\nFound {len(extra_in_db)} transactions in database not in manual verification:")
    print(f"{'Date':<12} {'Description':<45} {'Debit':>12} {'Credit':>12} {'Balance':>12}")
    print("-" * 80)
    for t in extra_in_db[:20]:  # Show first 20
        print(f"{t['date']:<12} {t['description'][:44]:<45} "
              f"${t['debit']:>10,.2f} ${t['credit']:>10,.2f} ${t['balance']:>10,.2f}")
    
    if len(extra_in_db) > 20:
        print(f"... and {len(extra_in_db) - 20} more")
else:
    print("\n[OK] No extra transactions in database")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Manual verification: {len(manual_txns)} transactions")
print(f"Database: {len(db_txns)} transactions")
print(f"Missing from DB: {len(missing_from_db)}")
print(f"Extra in DB: {len(extra_in_db)}")
print(f"\nConclusion: {'[OK] VERIFIED' if len(missing_from_db) == 0 and len(extra_in_db) == 0 else '[WARN] DISCREPANCIES FOUND'}")

cur.close()
conn.close()
