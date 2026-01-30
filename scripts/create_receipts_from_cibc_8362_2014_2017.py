"""
Create receipts from CIBC 8362 2014-2017 banking transactions
Creates receipts for ALL debit transactions
Does NOT delete any banking_transactions records
"""
import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password='***REDACTED***'
)
cur = conn.cursor()

print("=" * 100)
print("CREATE RECEIPTS FROM CIBC 8362 (2014-2017) BANKING TRANSACTIONS")
print("=" * 100)

# Get all debit transactions (expenses) that don't have receipts yet
cur.execute("""
    SELECT 
        bt.transaction_id,
        bt.transaction_date,
        bt.description,
        bt.debit_amount,
        bt.credit_amount
    FROM banking_transactions bt
    LEFT JOIN receipts r ON r.banking_transaction_id = bt.transaction_id
    WHERE bt.bank_id = 1
    AND bt.source_file = '2014-2017 CIBC 8362.xlsx'
    AND bt.debit_amount IS NOT NULL
    AND bt.debit_amount > 0
    AND r.receipt_id IS NULL
    ORDER BY bt.transaction_date, bt.transaction_id
""")

transactions = cur.fetchall()

print(f"\n📊 Found {len(transactions):,} debit transactions to create receipts for\n")

if len(transactions) == 0:
    print("✅ All transactions already have receipts")
    cur.close()
    conn.close()
    exit(0)

# Show sample
print("Sample transactions (first 10):")
print(f"{'Date':<12} {'ID':<8} {'Amount':<12} {'Description':<50}")
print("-" * 100)
for i, (tid, date, desc, debit, credit) in enumerate(transactions[:10]):
    print(f"{str(date):<12} {tid:<8} ${debit:>9.2f}   {desc[:50]}")
if len(transactions) > 10:
    print(f"... and {len(transactions) - 10:,} more")

response = input(f"\nCreate {len(transactions):,} receipts? (YES to proceed): ")

if response != "YES":
    print("❌ Cancelled")
    cur.close()
    conn.close()
    exit(0)

print("\n🚀 Creating receipts...")

created = 0
skipped = 0
errors = 0

for tid, date, desc, debit, credit in transactions:
    try:
        # Create receipt from banking transaction
        cur.execute("""
            INSERT INTO receipts (
                receipt_date,
                vendor_name,
                gross_amount,
                category,
                description,
                banking_transaction_id,
                created_from_banking,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, true, NOW())
        """, (
            date,
            desc[:255] if desc else 'Unknown',  # vendor_name from description
            debit,
            'Uncategorized',  # will categorize later
            f'Auto-created from banking (CIBC 8362 2014-2017)',
            tid
        ))
        
        created += 1
        
        if created % 500 == 0:
            print(f"  Created {created:,} receipts...")
            
    except Exception as e:
        errors += 1
        print(f"❌ Error creating receipt for transaction {tid}: {e}")
        if errors > 10:
            print("Too many errors, stopping...")
            conn.rollback()
            break

if errors == 0:
    conn.commit()
    print(f"\n✅ COMMITTED {created:,} receipts to database")
else:
    conn.rollback()
    print(f"\n❌ ROLLED BACK due to {errors} errors")

# Verify
cur.execute("""
    SELECT COUNT(*)
    FROM receipts
    WHERE created_from_banking = true
    AND banking_transaction_id IN (
        SELECT transaction_id
        FROM banking_transactions
        WHERE bank_id = 1
        AND source_file = '2014-2017 CIBC 8362.xlsx'
    )
""")

total_receipts = cur.fetchone()[0]

print("\n" + "=" * 100)
print("VERIFICATION")
print("=" * 100)
print(f"Total receipts from CIBC 8362 (2014-2017): {total_receipts:,}")
print(f"Created this run: {created:,}")
print(f"Errors: {errors}")

cur.close()
conn.close()

print("\n✅ Receipt creation complete")
print("\nNOTE: NO banking_transactions were deleted - all preserved as source records")
