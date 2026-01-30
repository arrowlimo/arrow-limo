"""
Create receipts for all banking transactions and link them.
This handles the categorized banking transactions we've identified.
"""

import psycopg2
from datetime import datetime
import hashlib

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
print("CREATING RECEIPTS FOR BANKING TRANSACTIONS")
print("=" * 80)
print()

# Step 1: Check receipts table structure
print("Step 1: Checking receipts table structure...")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'receipts' 
    ORDER BY ordinal_position
""")
receipt_columns = cur.fetchall()
print(f"Found {len(receipt_columns)} columns in receipts table")
for col, dtype in receipt_columns:
    print(f"  {col:30} {dtype}")
print()

# Step 2: Add receipt_id column to banking_transactions if it doesn't exist
print("Step 2: Adding receipt_id column to banking_transactions...")
cur.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'banking_transactions' 
    AND column_name = 'receipt_id'
""")
has_receipt_id = cur.fetchone() is not None

if not has_receipt_id:
    print("  Adding receipt_id column...")
    cur.execute("""
        ALTER TABLE banking_transactions 
        ADD COLUMN receipt_id INTEGER REFERENCES receipts(id)
    """)
    cur.execute("""
        CREATE INDEX idx_banking_receipt_id ON banking_transactions(receipt_id)
    """)
    conn.commit()
    print("  ✓ Added receipt_id column and index")
else:
    print("  ✓ receipt_id column already exists")
print()

# Step 3: Define categories and their GL mappings
print("Step 3: Defining banking transaction categories...")

categories = [
    {
        "name": "Banking Fees",
        "condition": "description ILIKE '%fee%' OR description ILIKE '%service charge%' OR description ILIKE '%nsf%'",
        "expense_type": "Bank Service Charges",
        "gl_account": "5400",
        "vendor": "Royal Bank of Canada",
        "payment_method": "Bank Debit"
    },
    {
        "name": "Rent Payments",
        "condition": "description ILIKE '%rent%'",
        "expense_type": "Rent",
        "gl_account": "5200",
        "vendor": "Landlord",
        "payment_method": "Bank Transfer"
    },
    {
        "name": "Utilities - Telus",
        "condition": "description ILIKE '%telus%'",
        "expense_type": "Telephone & Internet",
        "gl_account": "5700",
        "vendor": "Telus",
        "payment_method": "Bank Debit"
    },
    {
        "name": "Utilities - Shaw",
        "condition": "description ILIKE '%shaw%'",
        "expense_type": "Telephone & Internet",
        "gl_account": "5700",
        "vendor": "Shaw",
        "payment_method": "Bank Debit"
    },
    {
        "name": "Money Mart",
        "condition": "description ILIKE '%money mart%'",
        "expense_type": "Bank Service Charges",
        "gl_account": "5400",
        "vendor": "Money Mart",
        "payment_method": "Bank Debit"
    },
    {
        "name": "Heffner Vehicle Payments",
        "condition": "description ILIKE '%heffner%'",
        "expense_type": "Vehicle Lease Payments",
        "gl_account": "5600",
        "vendor": "Heffner",
        "payment_method": "Bank Debit"
    },
    {
        "name": "David Richard - Loan Repayments",
        "condition": "description ILIKE '%david%richard%' OR description ILIKE '%davidwr%' AND credit_amount = 0 AND debit_amount > 0",
        "expense_type": "Loan Repayment",
        "gl_account": "2120",
        "vendor": "David Richard",
        "payment_method": "E-Transfer"
    },
]

print(f"  Defined {len(categories)} categories")
print()

# Step 4: Create receipts for each category
print("Step 4: Creating receipts for each category...")
print()

total_receipts_created = 0
total_amount = 0

for category in categories:
    print(f"\nProcessing: {category['name']}")
    print("-" * 80)
    
    # Get transactions for this category
    cur.execute(f"""
        SELECT 
            transaction_id,
            transaction_date,
            description,
            debit_amount,
            account_number
        FROM banking_transactions
        WHERE debit_amount > 0
        AND receipt_id IS NULL
        AND ({category['condition']})
        ORDER BY transaction_date
    """)
    
    transactions = cur.fetchall()
    print(f"  Found {len(transactions)} transactions")
    
    if len(transactions) == 0:
        continue
    
    category_total = 0
    created_count = 0
    
    for txn_id, txn_date, description, amount, account_num in transactions:
        # Create unique hash for this receipt
        hash_string = f"banking_{txn_id}_{txn_date}_{amount}_{description}"
        source_hash = hashlib.sha256(hash_string.encode()).hexdigest()[:64]
        
        # Create receipt
        try:
            cur.execute("""
                INSERT INTO receipts (
                    receipt_date,
                    vendor_name,
                    gross_amount,
                    description,
                    payment_method,
                    expense_account,
                    created_from_banking,
                    source_system,
                    source_reference,
                    source_hash
                )
                VALUES (%s, %s, %s, %s, %s, %s, TRUE, 'banking_import', %s, %s)
                RETURNING id
            """, (
                txn_date,
                category['vendor'],
                amount,
                description[:500] if description else category['name'],
                category['payment_method'],
                category['gl_account'],
                f"BTX_{txn_id}",
                source_hash
            ))
            
            receipt_id = cur.fetchone()[0]
            
            # Link banking transaction to receipt
            cur.execute("""
                UPDATE banking_transactions
                SET receipt_id = %s
                WHERE transaction_id = %s
            """, (receipt_id, txn_id))
            
            created_count += 1
            category_total += float(amount)
            
        except Exception as e:
            print(f"  Error creating receipt for transaction {txn_id}: {e}")
            continue
    
    conn.commit()
    
    print(f"  ✓ Created {created_count} receipts")
    print(f"  ✓ Total amount: ${category_total:,.2f}")
    
    total_receipts_created += created_count
    total_amount += category_total

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total receipts created: {total_receipts_created:,}")
print(f"Total amount: ${total_amount:,.2f}")
print()

# Verify
cur.execute("""
    SELECT COUNT(*), SUM(debit_amount)
    FROM banking_transactions
    WHERE debit_amount > 0
    AND receipt_id IS NULL
""")
remaining_count, remaining_amount = cur.fetchone()
print(f"Remaining transactions without receipts: {remaining_count:,}")
if remaining_amount:
    print(f"Remaining amount: ${remaining_amount:,.2f}")
print()

print("✓ Banking receipt creation complete!")

cur.close()
conn.close()
