#!/usr/bin/env python3
"""Create receipts for David loan etransfers and track all David transactions."""

import psycopg2
import sys
from datetime import datetime
import hashlib

# Check for --write flag
DRY_RUN = '--write' not in sys.argv

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REMOVED***'
)
cur = conn.cursor()

print("="*120)
print("DAVID RICHARD LOAN TRACKING")
print("="*120)
print(f"Mode: {'DRY RUN' if DRY_RUN else 'WRITE MODE'}\n")

# Step 1: Get all David Richard banking transactions
cur.execute("""
    SELECT transaction_id, transaction_date, description, 
           debit_amount, credit_amount, account_number, balance
    FROM banking_transactions
    WHERE description ILIKE '%david richard%'
    ORDER BY transaction_date, transaction_id
""")

transactions = cur.fetchall()
print(f"Found {len(transactions)} banking transactions with 'David Richard'")

# Separate into loans (credits) and payments (debits)
loans_received = []
payments_made = []

for t in transactions:
    txn_id, date, desc, debit, credit, account, balance = t
    if credit and credit > 0:
        loans_received.append(t)
    elif debit and debit > 0:
        payments_made.append(t)

print(f"\nLoans received (credits): {len(loans_received)} totaling ${sum(t[4] for t in loans_received):,.2f}")
print(f"Payments made (debits): {len(payments_made)} totaling ${sum(t[3] for t in payments_made):,.2f}")

# Check if Notes Payable - David account exists
cur.execute("""
    SELECT account_code, account_name
    FROM chart_of_accounts
    WHERE account_code = '2020'
""")
notes_payable = cur.fetchone()

if not notes_payable:
    print("\n⚠️  Account 2020 (Notes Payable - David) does not exist")
    print("Creating account 2020...")
    
    if not DRY_RUN:
        cur.execute("""
            INSERT INTO chart_of_accounts (account_code, account_name, account_type, description)
            VALUES ('2020', 'Notes Payable - David', 'Liabilities', 'Loans from David Richard')
        """)
        print("✓ Created account 2020")
else:
    print(f"\n✓ Account 2020 exists: {notes_payable[1]}")

# Step 2: Check for existing receipts
cur.execute("""
    SELECT source_hash FROM receipts WHERE source_hash IS NOT NULL
""")
existing_hashes = {row[0] for row in cur.fetchall()}
print(f"\nExisting receipt hashes: {len(existing_hashes)}")

# Step 3: Create receipts for loan transactions
print("\n" + "="*120)
print("LOAN RECEIPTS (Credits - Money Received)")
print("="*120)

receipts_to_create = []
receipts_skipped = 0

for t in loans_received:
    txn_id, date, desc, debit, credit, account, balance = t
    
    # Generate hash
    hash_input = f"{date}|{desc}|{credit:.2f}".encode('utf-8')
    source_hash = hashlib.sha256(hash_input).hexdigest()
    
    if source_hash in existing_hashes:
        receipts_skipped += 1
        continue
    
    receipts_to_create.append({
        'date': date,
        'vendor': 'David Richard',
        'amount': credit,
        'description': f'Loan from David Richard - {desc[:50]}',
        'category': 'loan_received',
        'gl_code': '2020',  # Notes Payable liability
        'banking_id': txn_id,
        'hash': source_hash,
        'type': 'loan'
    })

print(f"Receipts to create: {len(receipts_to_create)}")
print(f"Receipts already exist: {receipts_skipped}")

# Step 4: Create receipts for payment transactions
print("\n" + "="*120)
print("PAYMENT RECEIPTS (Debits - Loan Repayments)")
print("="*120)

payment_receipts = []
payment_skipped = 0

for t in payments_made:
    txn_id, date, desc, debit, credit, account, balance = t
    
    # Generate hash
    hash_input = f"{date}|{desc}|{debit:.2f}".encode('utf-8')
    source_hash = hashlib.sha256(hash_input).hexdigest()
    
    if source_hash in existing_hashes:
        payment_skipped += 1
        continue
    
    payment_receipts.append({
        'date': date,
        'vendor': 'David Richard',
        'amount': debit,
        'description': f'Loan repayment to David Richard - {desc[:50]}',
        'category': 'loan_payment',
        'gl_code': '2020',  # Reduces Notes Payable liability
        'banking_id': txn_id,
        'hash': source_hash,
        'type': 'payment'
    })

print(f"Payment receipts to create: {len(payment_receipts)}")
print(f"Payment receipts already exist: {payment_skipped}")

# Summary
print("\n" + "="*120)
print("SUMMARY")
print("="*120)
print(f"Total receipts to create: {len(receipts_to_create) + len(payment_receipts)}")
print(f"  - Loan receipts: {len(receipts_to_create)} (${sum(r['amount'] for r in receipts_to_create):,.2f})")
print(f"  - Payment receipts: {len(payment_receipts)} (${sum(r['amount'] for r in payment_receipts):,.2f})")

if DRY_RUN:
    print("\n⚠️  DRY RUN MODE - No changes made")
    print("Run with --write flag to apply changes")
    
    # Show sample of what would be created
    print("\nSample loan receipts (first 5):")
    for r in receipts_to_create[:5]:
        print(f"  {r['date']} ${r['amount']:>9.2f} - {r['description'][:70]}")
    
    print("\nSample payment receipts (first 5):")
    for r in payment_receipts[:5]:
        print(f"  {r['date']} ${r['amount']:>9.2f} - {r['description'][:70]}")
else:
    print("\n✍️  CREATING RECEIPTS...")
    
    created_count = 0
    
    # Create loan receipts
    for r in receipts_to_create:
        # Skip if hash already exists (shouldn't happen but double-check)
        if r['hash'] in existing_hashes:
            continue
        
        # Get account number for this banking transaction
        cur.execute("SELECT account_number FROM banking_transactions WHERE transaction_id = %s", (r['banking_id'],))
        account_result = cur.fetchone()
        account_number = account_result[0] if account_result else '0228362'
        
        # Determine mapped_bank_account_id
        if account_number == '0228362':
            mapped_bank_account_id = 1
        else:
            mapped_bank_account_id = 2
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                description, category, gl_account_code, 
                created_from_banking, mapped_bank_account_id, source_hash,
                auto_categorized
            ) VALUES (
                %s, %s, %s, 0, %s, %s, %s, %s, TRUE, %s, %s, TRUE
            ) RETURNING receipt_id
        """, (r['date'], r['vendor'], r['amount'], r['amount'], r['description'],
              r['category'], r['gl_code'], mapped_bank_account_id, r['hash']))
        
        receipt_id = cur.fetchone()[0]
        existing_hashes.add(r['hash'])
        
        # Link to banking transaction
        cur.execute("""
            INSERT INTO banking_receipt_matching_ledger (
                banking_transaction_id, receipt_id, match_date,
                match_type, match_status, match_confidence,
                notes, created_by
            ) VALUES (%s, %s, CURRENT_DATE, 'loan_received', 'matched', '100',
                     'Loan received from David Richard', 'system')
        """, (r['banking_id'], receipt_id))
        
        created_count += 1
    
    # Create payment receipts
    for r in payment_receipts:
        # Skip if hash already exists (shouldn't happen but double-check)
        if r['hash'] in existing_hashes:
            continue
        
        # Get account number for this banking transaction
        cur.execute("SELECT account_number FROM banking_transactions WHERE transaction_id = %s", (r['banking_id'],))
        account_result = cur.fetchone()
        account_number = account_result[0] if account_result else '0228362'
        
        # Determine mapped_bank_account_id
        if account_number == '0228362':
            mapped_bank_account_id = 1
        else:
            mapped_bank_account_id = 2
        
        cur.execute("""
            INSERT INTO receipts (
                receipt_date, vendor_name, gross_amount, gst_amount, net_amount,
                description, category, gl_account_code,
                created_from_banking, mapped_bank_account_id, source_hash,
                auto_categorized
            ) VALUES (
                %s, %s, %s, 0, %s, %s, %s, %s, TRUE, %s, %s, TRUE
            ) RETURNING receipt_id
        """, (r['date'], r['vendor'], r['amount'], r['amount'], r['description'],
              r['category'], r['gl_code'], mapped_bank_account_id, r['hash']))
        
        receipt_id = cur.fetchone()[0]
        existing_hashes.add(r['hash'])
        
        # Link to banking transaction
        cur.execute("""
            INSERT INTO banking_receipt_matching_ledger (
                banking_transaction_id, receipt_id, match_date,
                match_type, match_status, match_confidence,
                notes, created_by
            ) VALUES (%s, %s, CURRENT_DATE, 'loan_payment', 'matched', '100',
                     'Loan payment to David Richard', 'system')
        """, (r['banking_id'], receipt_id))
        
        created_count += 1
    
    conn.commit()
    print(f"✓ Created {created_count} receipts")

# Step 5: Calculate running loan balance
print("\n" + "="*120)
print("DAVID LOAN LEDGER (Running Balance)")
print("="*120)
print(f"{'Date':12s} | {'Type':10s} | {'Amount':>10s} | {'Balance':>12s} | Description")
print("-"*120)

# Get all David transactions chronologically
cur.execute("""
    SELECT transaction_date, description, debit_amount, credit_amount
    FROM banking_transactions
    WHERE description ILIKE '%david richard%'
    ORDER BY transaction_date, transaction_id
""")

all_david = cur.fetchall()
running_balance = 0

for t in all_david:
    date, desc, debit, credit = t
    if credit and credit > 0:
        # Loan received - increases liability
        running_balance += credit
        txn_type = 'LOAN'
        amount = credit
    elif debit and debit > 0:
        # Payment made - decreases liability
        running_balance -= debit
        txn_type = 'PAYMENT'
        amount = -debit
    else:
        continue
    
    print(f"{date!s:12s} | {txn_type:10s} | ${amount:>9.2f} | ${running_balance:>11.2f} | {desc[:50]}")

print("-"*120)
print(f"{'FINAL BALANCE':12s} | {'':10s} | {'':>10s} | ${running_balance:>11.2f} |")

if running_balance > 0:
    print(f"\n⚠️  Outstanding loan balance: ${running_balance:,.2f}")
elif running_balance < 0:
    print(f"\n⚠️  Overpayment: ${abs(running_balance):,.2f} (paid more than borrowed)")
else:
    print(f"\n✅ Loan fully repaid - balance is $0.00")

conn.close()
