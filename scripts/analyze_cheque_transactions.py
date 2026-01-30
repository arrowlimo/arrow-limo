#!/usr/bin/env python3
"""Check the 34 'Cheque' transactions to see if they're Heffner or QuickBooks artifacts."""

import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="almsdata",
    user="postgres",
    password="***REDACTED***"
)

cur = conn.cursor()

print("=" * 100)
print("ANALYZING 34 'CHEQUE' CREDIT TRANSACTIONS")
print("=" * 100)

# Get all credit transactions starting with "Cheque"
cur.execute("""
    SELECT 
        bt.transaction_date,
        bt.account_number,
        bt.description,
        bt.credit_amount
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM receipts r 
          WHERE r.banking_transaction_id = bt.transaction_id
      )
      AND bt.description LIKE 'Cheque%'
    ORDER BY bt.transaction_date
""")

transactions = cur.fetchall()

print(f"\nFound {len(transactions)} transactions starting with 'Cheque'")
print("\n" + "-" * 100)

# Check for Heffner pattern
heffner_count = 0
heffner_2525_count = 0
other_count = 0

for date, account, desc, amount in transactions:
    is_heffner = 'HEFFNER' in desc.upper() or 'LEXUS' in desc.upper() or 'TOYOTA' in desc.upper()
    is_2525 = abs(float(amount) - 2525.25) < 0.01
    
    if is_heffner:
        heffner_count += 1
        if is_2525:
            heffner_2525_count += 1
        icon = "🚗 HEFFNER"
    else:
        other_count += 1
        icon = "📄 OTHER"
    
    print(f"{icon} | {date} | {account:12s} | ${amount:10.2f} | {desc}")

print("\n" + "=" * 100)
print("SUMMARY")
print("=" * 100)
print(f"Total 'Cheque' transactions: {len(transactions)}")
print(f"  Heffner-related: {heffner_count} (${sum(t[3] for t in transactions if 'HEFFNER' in t[2].upper() or 'LEXUS' in t[2].upper() or 'TOYOTA' in t[2].upper()):,.2f})")
print(f"    Amount = $2525.25: {heffner_2525_count}")
print(f"  Other: {other_count}")

# Show unique description patterns
print("\n" + "=" * 100)
print("DESCRIPTION PATTERNS (after 'Cheque ')")
print("=" * 100)

cur.execute("""
    SELECT 
        SUBSTRING(bt.description FROM 8) as detail_part,
        COUNT(*) as count,
        SUM(bt.credit_amount) as total_amount
    FROM banking_transactions bt
    WHERE bt.credit_amount > 0
      AND NOT EXISTS (
          SELECT 1 FROM receipts r 
          WHERE r.banking_transaction_id = bt.transaction_id
      )
      AND bt.description LIKE 'Cheque%'
    GROUP BY detail_part
    ORDER BY count DESC
""")

print(f"\nDetail After 'Cheque' Prefix | Count | Total Amount")
print("-" * 70)
for detail, count, amount in cur.fetchall():
    print(f"{detail[:40]:40s} | {count:5d} | ${amount:10.2f}")

cur.close()
conn.close()
