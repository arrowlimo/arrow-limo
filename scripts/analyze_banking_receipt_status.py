"""
Analyze which banking transactions have receipts and which still need them.
Focus on the categories we identified: banking fees, e-transfers, withdrawals, etc.
"""

import psycopg2
from datetime import datetime

# Database connection
conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="***REDACTED***",
    host="localhost",
    port="5432"
)
cur = conn.cursor()

print("=" * 80)
print("BANKING TRANSACTIONS - RECEIPT STATUS ANALYSIS")
print("=" * 80)
print()

# Get total banking transactions (expenses = debits)
cur.execute("""
    SELECT COUNT(*), SUM(debit_amount)
    FROM banking_transactions
    WHERE debit_amount > 0  -- Expenses (debits)
""")
total_count, total_amount = cur.fetchone()
print(f"Total Banking Expense Transactions: {total_count:,}")
print(f"Total Amount: ${total_amount:,.2f}")
print()

# Check if receipt_id column exists
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    AND column_name = 'receipt_id'
""")
has_receipt_id = cur.fetchone() is not None

if not has_receipt_id:
    print("NOTE: banking_transactions does not have a receipt_id column yet")
    print("      Need to add this column to link transactions to receipts")
    print()

# Check which banking transactions have receipts (if column exists)
print("=" * 80)
print("RECEIPT MATCHING STATUS")
print("=" * 80)
print()

if has_receipt_id:
    cur.execute("""
        SELECT 
            CASE 
                WHEN bt.receipt_id IS NOT NULL THEN 'Has Receipt'
                ELSE 'No Receipt'
            END as status,
            COUNT(*) as count,
            SUM(bt.debit_amount) as total_amount
        FROM banking_transactions bt
        WHERE bt.debit_amount > 0  -- Expenses (debits)
        GROUP BY status
        ORDER BY status
    """)
else:
    print("Cannot check receipt status - receipt_id column doesn't exist")
    print()
    cur.execute("""
        SELECT 
            'No Receipt' as status,
            COUNT(*) as count,
            SUM(debit_amount) as total_amount
        FROM banking_transactions
        WHERE debit_amount > 0
    """)

for status, count, amount in cur.fetchall():
    print(f"{status:20} {count:8,} transactions    ${amount:15,.2f}")

print()

# Analyze by transaction type/description patterns
print("=" * 80)
print("TRANSACTIONS WITHOUT RECEIPTS - BY CATEGORY")
print("=" * 80)
print()

categories = [
    ("Banking Fees", "description ILIKE '%fee%' OR description ILIKE '%charge%'"),
    ("E-Transfers Sent", "description ILIKE '%e-transfer%' OR description ILIKE '%etransfer%' OR description ILIKE '%interac%'"),
    ("ATM Withdrawals", "description ILIKE '%atm%' OR description ILIKE '%withdrawal%' OR description ILIKE '%cash%'"),
    ("Transfers Between Accounts", "description ILIKE '%transfer%' AND description NOT ILIKE '%e-transfer%'"),
    ("Credit Card Payments", "description ILIKE '%visa%' OR description ILIKE '%mastercard%' OR description ILIKE '%credit card%'"),
    ("Money Mart", "description ILIKE '%money mart%'"),
    ("Heffner", "description ILIKE '%heffner%'"),
    ("Rent Payments", "description ILIKE '%rent%'"),
    ("Internet/Phone", "description ILIKE '%telus%' OR description ILIKE '%shaw%' OR description ILIKE '%bell%'"),
    ("David Richard E-Transfers", "description ILIKE '%david%' OR description ILIKE '%davidwr%'"),
]

for category_name, condition in categories:
    if has_receipt_id:
        cur.execute(f"""
            SELECT 
                COUNT(*) as count,
                SUM(debit_amount) as total_amount,
                COUNT(CASE WHEN receipt_id IS NOT NULL THEN 1 END) as with_receipt,
                COUNT(CASE WHEN receipt_id IS NULL THEN 1 END) as without_receipt
            FROM banking_transactions
            WHERE debit_amount > 0  -- Expenses (debits)
            AND ({condition})
        """)
    else:
        cur.execute(f"""
            SELECT 
                COUNT(*) as count,
                SUM(debit_amount) as total_amount,
                0 as with_receipt,
                COUNT(*) as without_receipt
            FROM banking_transactions
            WHERE debit_amount > 0  -- Expenses (debits)
            AND ({condition})
        """)
    
    count, total_amount, with_receipt, without_receipt = cur.fetchone()
    
    if count and count > 0:
        print(f"\n{category_name}:")
        print(f"  Total transactions: {count:,}")
        print(f"  Total amount: ${total_amount:,.2f}")
        print(f"  With receipts: {with_receipt:,}")
        print(f"  WITHOUT receipts: {without_receipt:,}")
        if without_receipt > 0:
            pct = (without_receipt / count) * 100
            print(f"  Missing: {pct:.1f}%")

print()
print("=" * 80)
print("SAMPLE TRANSACTIONS WITHOUT RECEIPTS")
print("=" * 80)
print()

# Show examples of transactions without receipts from each category
for category_name, condition in categories[:5]:  # First 5 categories
    if has_receipt_id:
        cur.execute(f"""
            SELECT 
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE debit_amount > 0  -- Expenses (debits)
            AND receipt_id IS NULL
            AND ({condition})
            ORDER BY debit_amount DESC
            LIMIT 3
        """)
    else:
        cur.execute(f"""
            SELECT 
                transaction_date,
                description,
                debit_amount
            FROM banking_transactions
            WHERE debit_amount > 0  -- Expenses (debits)
            AND ({condition})
            ORDER BY debit_amount DESC
            LIMIT 3
        """)
    
    results = cur.fetchall()
    if results:
        print(f"\n{category_name} (samples):")
        for date, desc, amount in results:
            print(f"  {date} | ${amount:8.2f} | {desc[:60]}")

print()
print("=" * 80)
print("RECEIPTS TABLE ANALYSIS")
print("=" * 80)
print()

# Check what's in the receipts table
cur.execute("""
    SELECT 
        expense_type,
        COUNT(*) as count,
        SUM(amount) as total_amount
    FROM receipts
    GROUP BY expense_type
    ORDER BY count DESC
    LIMIT 20
""")

print("\nReceipts by Expense Type:")
for expense_type, count, amount in cur.fetchall():
    if amount:
        print(f"  {expense_type:40} {count:6,} receipts    ${amount:12,.2f}")
    else:
        print(f"  {expense_type:40} {count:6,} receipts    (no amount)")

# Check if there are any "Banking Fee" or similar receipts
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE expense_type ILIKE '%bank%'
       OR expense_type ILIKE '%fee%'
       OR expense_type ILIKE '%transfer%'
""")
banking_receipt_count = cur.fetchone()[0]
print(f"\nReceipts with banking-related expense types: {banking_receipt_count:,}")

print()
print("=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print()

# Count how many need receipts
if has_receipt_id:
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount)
        FROM banking_transactions
        WHERE debit_amount > 0  -- Expenses (debits)
        AND receipt_id IS NULL
    """)
    no_receipt_count, no_receipt_amount = cur.fetchone()
else:
    cur.execute("""
        SELECT COUNT(*), SUM(debit_amount)
        FROM banking_transactions
        WHERE debit_amount > 0  -- Expenses (debits)
    """)
    no_receipt_count, no_receipt_amount = cur.fetchone()

print(f"Total transactions needing receipts: {no_receipt_count:,}")
print(f"Total amount needing receipts: ${no_receipt_amount:,.2f}")
print()

print("Next Steps:")
print("1. Create receipts for all categorized banking transactions")
print("2. Link banking_transactions to receipts via receipt_id")
print("3. Categories to create receipts for:")
print("   - Banking fees")
print("   - E-transfers (to/from David Richard)")
print("   - ATM withdrawals")
print("   - Credit card payments")
print("   - Money Mart payments")
print("   - Heffner vehicle payments")
print("   - Rent payments")
print("   - Internet/phone utilities")

cur.close()
conn.close()
