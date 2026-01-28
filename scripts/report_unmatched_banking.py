#!/usr/bin/env python3
"""
Report on unmatched banking transactions after receipt matching.
"""

import os
import psycopg2
import csv

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'almsdata'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', '***REMOVED***')
    )

print("=" * 100)
print("UNMATCHED BANKING TRANSACTIONS REPORT")
print("=" * 100)

conn = get_db_connection()
cur = conn.cursor()

# Get unmatched debits (expenses without receipts)
cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        debit_amount,
        category
    FROM banking_transactions
    WHERE debit_amount > 0
      AND EXTRACT(YEAR FROM transaction_date) = 2012
      AND NOT EXISTS (
          SELECT 1 FROM receipts 
          WHERE mapped_bank_account_id = transaction_id
      )
    ORDER BY debit_amount DESC, transaction_date
""")

unmatched_debits = cur.fetchall()

print(f"\n[1] UNMATCHED DEBIT TRANSACTIONS (Expenses without receipts)")
print(f"    Total: {len(unmatched_debits)} transactions")

if unmatched_debits:
    total_amount = sum(t[4] for t in unmatched_debits)
    print(f"    Total amount: ${total_amount:,.2f}")
    
    # Group by description pattern
    patterns = {}
    for trans in unmatched_debits:
        desc = trans[3] or ''
        
        # Categorize by common patterns
        if 'TRANSFER' in desc.upper():
            category = 'Transfer'
        elif 'DEPOSIT' in desc.upper() or 'DEP' in desc.upper():
            category = 'Deposit-related'
        elif 'PAYMENT' in desc.upper() or 'PMT' in desc.upper():
            category = 'Payment'
        elif 'CHEQUE' in desc.upper() or 'CHQ' in desc.upper() or 'CHECK' in desc.upper():
            category = 'Cheque'
        elif 'DEBIT' in desc.upper() or 'PAD' in desc.upper():
            category = 'Pre-authorized debit'
        elif 'LEASE' in desc.upper() or 'RENT' in desc.upper():
            category = 'Lease/Rent'
        elif 'PURCHASE' in desc.upper() or 'POS' in desc.upper():
            category = 'Point of sale'
        else:
            category = 'Other'
        
        if category not in patterns:
            patterns[category] = []
        patterns[category].append(trans)
    
    print(f"\n    By category:")
    for category in sorted(patterns.keys()):
        trans_list = patterns[category]
        cat_total = sum(t[4] for t in trans_list)
        print(f"      {category}: {len(trans_list)} transactions, ${cat_total:,.2f}")
    
    # Show highest value unmatched
    print(f"\n    Top 20 highest value unmatched debits:")
    print(f"    {'ID':>8} | {'Date':10} | {'Amount':>12} | Description")
    print(f"    {'-'*8}-+-{'-'*10}-+-{'-'*12}-+-{'-'*60}")
    for trans in unmatched_debits[:20]:
        trans_id, account, date, desc, amount, cat = trans
        print(f"    {trans_id:8} | {date} | ${amount:>11.2f} | {desc[:60]}")

# Get unmatched credits (income without tracking)
cur.execute("""
    SELECT 
        transaction_id,
        account_number,
        transaction_date,
        description,
        credit_amount
    FROM banking_transactions
    WHERE credit_amount > 0
      AND EXTRACT(YEAR FROM transaction_date) = 2012
      AND NOT EXISTS (
          SELECT 1 FROM receipts 
          WHERE mapped_bank_account_id = transaction_id
      )
    ORDER BY credit_amount DESC, transaction_date
""")

unmatched_credits = cur.fetchall()

print(f"\n\n[2] UNMATCHED CREDIT TRANSACTIONS (Income deposits without receipts)")
print(f"    Total: {len(unmatched_credits)} transactions")

if unmatched_credits:
    total_amount = sum(t[4] for t in unmatched_credits)
    print(f"    Total amount: ${total_amount:,.2f}")
    
    print(f"\n    Top 20 highest value unmatched credits:")
    print(f"    {'ID':>8} | {'Date':10} | {'Amount':>12} | Description")
    print(f"    {'-'*8}-+-{'-'*10}-+-{'-'*12}-+-{'-'*60}")
    for trans in unmatched_credits[:20]:
        trans_id, account, date, desc, amount = trans
        print(f"    {trans_id:8} | {date} | ${amount:>11.2f} | {desc[:60]}")

# Save full report to CSV
print(f"\n\n[3] Saving detailed reports...")

os.makedirs('reports', exist_ok=True)

# Unmatched debits CSV
with open('reports/unmatched_debits_2012.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Transaction ID', 'Account', 'Date', 'Description', 'Amount', 'Category'])
    for trans in unmatched_debits:
        writer.writerow(trans)

print(f"    ✓ reports/unmatched_debits_2012.csv ({len(unmatched_debits)} rows)")

# Unmatched credits CSV
with open('reports/unmatched_credits_2012.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Transaction ID', 'Account', 'Date', 'Description', 'Amount'])
    for trans in unmatched_credits:
        writer.writerow(trans)

print(f"    ✓ reports/unmatched_credits_2012.csv ({len(unmatched_credits)} rows)")

# Summary statistics
print(f"\n\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)

cur.execute("""
    SELECT 
        COUNT(*) as total_transactions,
        COUNT(CASE WHEN debit_amount > 0 THEN 1 END) as debit_count,
        COUNT(CASE WHEN credit_amount > 0 THEN 1 END) as credit_count,
        SUM(debit_amount) as total_debits,
        SUM(credit_amount) as total_credits
    FROM banking_transactions
    WHERE EXTRACT(YEAR FROM transaction_date) = 2012
""")

total_stats = cur.fetchone()

cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    JOIN banking_transactions bt ON r.mapped_bank_account_id = bt.transaction_id
    WHERE EXTRACT(YEAR FROM bt.transaction_date) = 2012
""")

matched_count = cur.fetchone()[0]

print(f"\n2012 Banking Transactions:")
print(f"  Total transactions: {total_stats[0]:,}")
print(f"  Debits: {total_stats[1]:,} (${total_stats[3]:,.2f})")
print(f"  Credits: {total_stats[2]:,} (${total_stats[4]:,.2f})")

print(f"\nMatching Status:")
print(f"  Matched to receipts: {matched_count:,}")
print(f"  Unmatched debits: {len(unmatched_debits):,} (${sum(t[4] for t in unmatched_debits):,.2f})")
print(f"  Unmatched credits: {len(unmatched_credits):,} (${sum(t[4] for t in unmatched_credits):,.2f})")

debit_match_rate = (matched_count / total_stats[1] * 100) if total_stats[1] > 0 else 0
print(f"  Debit match rate: {debit_match_rate:.1f}%")

cur.close()
conn.close()

print("\n" + "=" * 100)
