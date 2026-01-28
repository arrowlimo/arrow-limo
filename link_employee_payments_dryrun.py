#!/usr/bin/env python3
"""Link employee e-transfers and checks to employee pay/reimbursement records."""
import psycopg2
import os
from datetime import datetime, timedelta

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_NAME = os.environ.get('DB_NAME', 'almsdata')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', os.environ.get("DB_PASSWORD"))

DRY_RUN = True  # Set to False to execute

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "=" * 140)
print("LINK EMPLOYEE E-TRANSFERS & CHECKS TO EMPLOYEE PAY/REIMBURSEMENT".center(140))
if DRY_RUN:
    print("*** DRY RUN MODE ***".center(140))
print("=" * 140)

# Step 1: Get all employee e-transfers
EMPLOYEE_NAMES = ['PAUL RICHARD', 'SHERRI RYCKMAN', 'SHERRI', 'DAVID RICHARD', 'DAVID WILLIAM', 
                  'MICHAEL RICHARD', 'BARB', 'BARBARA', 'PEACOCK', 'JERRY', 'JEANNIE', 'MATTHEW']

cur.execute('''
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.credit_amount,
        bt.description,
        CASE 
            WHEN bt.description ILIKE '%ETRANSFER%' OR bt.description ILIKE '%E-TRANSFER%' THEN 'EFT'
            WHEN bt.description ILIKE '%CHQ%' OR bt.description ILIKE '%CHECK%' THEN 'CHQ'
            ELSE 'OTHER'
        END as txn_type
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND bt.reconciled_payment_id IS NULL
''')

all_banking = cur.fetchall()

# Filter for employee payments
employee_payments = []
for row in all_banking:
    trans_id, trans_date, amount, desc, txn_type = row
    if any(name in desc.upper() for name in EMPLOYEE_NAMES):
        employee_payments.append(row)

print(f"\n📊 Found {len(employee_payments)} employee payments (E-transfers + Checks)")
print(f"   Total: ${sum(e[2] for e in employee_payments):,.2f}\n")

# Categorize by type
etransfers = [e for e in employee_payments if e[4] == 'EFT']
checks = [e for e in employee_payments if e[4] == 'CHQ']

print(f"   E-Transfers: {len(etransfers)} | ${sum(e[2] for e in etransfers):,.2f}")
print(f"   Checks: {len(checks)} | ${sum(e[2] for e in checks):,.2f}\n")

# Step 2: Find NSF pairs (a debit matching a credit on same/adjacent dates with same amount)
# NSF = credit posted, then debit to reverse (bounced check)
nsf_pairs = []

for etransfer in employee_payments:
    trans_id, trans_date, amount, desc, txn_type = etransfer
    
    # Look for matching debit within ±3 days with same amount
    cur.execute('''
        SELECT transaction_id, transaction_date, debit_amount
        FROM banking_transactions
        WHERE debit_amount > 0
          AND ABS(debit_amount - %s) < 0.01
          AND transaction_date BETWEEN %s AND %s
    ''', (amount, trans_date - timedelta(days=3), trans_date + timedelta(days=3)))
    
    debits = cur.fetchall()
    if debits:
        # This is likely an NSF - credit posted then reversed
        nsf_pairs.append(etransfer)

print(f"⚠️  NSF pairs (credit + reversal debit): {len(nsf_pairs)} transactions")
print(f"   These will be EXCLUDED from employee pay linking\n")

# Filter out NSF pairs
valid_employee_payments = [e for e in employee_payments if e not in nsf_pairs]

print(f"✅ Valid employee payments (after NSF exclusion): {len(valid_employee_payments)}")
print(f"   Total: ${sum(e[2] for e in valid_employee_payments):,.2f}\n")

# Step 3: Link to employee pay records
# Strategy: Create/use an "Employee Pay & Reimbursement" reserve_number 
# OR check if employees have individual payment records

print("=" * 140)
print("SAMPLE EMPLOYEE PAYMENTS TO LINK (first 20):")
print("=" * 140)
print(f"{'Date':<12} | {'Amount':>10} | {'Type':<5} | Description (first 60 chars) | NSF?")
print("-" * 140)

for i, payment in enumerate(valid_employee_payments[:20]):
    trans_id, trans_date, amount, desc, txn_type = payment
    date_str = trans_date.strftime('%Y-%m-%d')
    is_nsf = '⚠️ NSF' if payment in nsf_pairs else 'OK'
    desc_short = desc[:60] if desc else 'N/A'
    print(f"{date_str} | ${amount:>9.2f} | {txn_type:<5} | {desc_short} | {is_nsf}")

if len(valid_employee_payments) > 20:
    print(f"... and {len(valid_employee_payments) - 20} more")

# Step 4: Create the linking update
print(f"\n" + "=" * 140)
print("NEXT STEP: Create or update 'Employee Pay & Reimbursement' reserve_number")
print("=" * 140)

print(f"""
Strategy:
1. Create a special charter/client for "EMPLOYEE PAY & REIMBURSEMENT" 
   (e.g., reserve_number = 'EMP_PAY' or similar)

2. Create payment records for {len(valid_employee_payments)} valid employee transactions
   - Link via reserve_number to the employee pay charter
   - Update banking_transactions.reconciled_payment_id to mark as linked

3. Exclude {len(nsf_pairs)} NSF pairs (reversals)

Would create:
  - {len(valid_employee_payments)} payment records
  - Total: ${sum(e[2] for e in valid_employee_payments):,.2f}
""")

print("=" * 140)
if DRY_RUN:
    print("💡 TO EXECUTE: Set DRY_RUN = False")
else:
    print("✅ READY TO EXECUTE")
print("=" * 140 + "\n")

cur.close()
conn.close()
