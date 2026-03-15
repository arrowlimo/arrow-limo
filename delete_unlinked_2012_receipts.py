"""
Delete 1,100 unlinked 2012 receipts (QuickBooks import artifacts)
All have NO banking_transaction_id link
"""

import psycopg2
from datetime import datetime

conn = psycopg2.connect(
    dbname="almsdata",
    user="postgres",
    password="ArrowLimousine",
    host="localhost"
)
conn.autocommit = False
cur = conn.cursor()

print("=" * 100)
print("DELETE UNLINKED 2012 RECEIPTS - QUICKBOOKS IMPORT ARTIFACTS")
print("=" * 100)
print()

# Get count and details
cur.execute("""
SELECT 
    COUNT(*) as total,
    SUM(gross_amount) as total_amount,
    COUNT(DISTINCT category) as categories
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date) = 2012
  AND banking_transaction_id IS NULL
""")

row = cur.fetchone()
delete_count, delete_amount, category_count = row

print(f"Receipts to delete: {delete_count}")
print(f"Total amount: ${delete_amount:,.2f}")
print(f"Categories affected: {category_count}")
print()

# Show category breakdown
cur.execute("""
SELECT 
    category,
    COUNT(*) as count,
    SUM(gross_amount) as amount
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date) = 2012
  AND banking_transaction_id IS NULL
GROUP BY category
ORDER BY COUNT(*) DESC
""")

print("Category Breakdown:")
print(f"{'Category':<30} {'Count':>8} {'Amount':>15}")
print("-" * 60)
for row in cur.fetchall():
    cat, count, amount = row
    print(f"{(cat or 'NULL')[:30]:<30} {count:>8} ${amount:>12,.2f}")

print()
print("=" * 100)

# Create backup table
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_table = f"receipts_backup_2012_unlinked_{timestamp}"

print(f"Creating backup table: {backup_table}")

cur.execute(f"""
CREATE TABLE {backup_table} AS
SELECT * FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date) = 2012
  AND banking_transaction_id IS NULL
""")

# Verify backup
cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
backup_count = cur.fetchone()[0]

print(f"✅ Backed up {backup_count} receipts to {backup_table}")
print()

# Ask for confirmation
response = input(f"DELETE {delete_count} unlinked 2012 receipts? (yes/no): ").strip().lower()

if response == 'yes':
    print()
    print("Deleting receipts...")
    
    # Delete the receipts
    cur.execute("""
    DELETE FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
      AND banking_transaction_id IS NULL
    """)
    
    deleted_count = cur.rowcount
    print(f"✅ Deleted {deleted_count} receipts")
    print()
    
    # Verify deletion
    cur.execute("""
    SELECT COUNT(*) FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
    """)
    remaining_2012 = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM receipts")
    total_receipts = cur.fetchone()[0]
    
    print("=" * 100)
    print("AFTER DELETION")
    print("=" * 100)
    print(f"Remaining 2012 receipts: {remaining_2012} (all with banking_transaction_id ✅)")
    print(f"Total receipts in database: {total_receipts}")
    print()
    
    commit = input("COMMIT deletion? (yes/no): ").strip().lower()
    if commit == 'yes':
        conn.commit()
        print("✅ Changes COMMITTED")
        print(f"📦 Backup table: {backup_table}")
    else:
        conn.rollback()
        print("❌ Changes ROLLED BACK")
else:
    print("❌ Deletion cancelled")
    conn.rollback()

print()
print("=" * 100)
print("FINAL SUMMARY")
print("=" * 100)

# Final count
cur.execute("""
SELECT 
    COUNT(*) as total,
    COUNT(banking_transaction_id) as linked,
    COUNT(*) - COUNT(banking_transaction_id) as unlinked
FROM receipts
WHERE EXTRACT(YEAR FROM receipt_date) = 2012
""")

row = cur.fetchone()
total, linked, unlinked = row

print(f"2012 Receipts:")
print(f"  Total: {total}")
if total > 0:
    print(f"  Linked to banking: {linked} ({linked/total*100:.1f}%)")
else:
    print(f"  Linked to banking: {linked} (0.0%)")
print(f"  Not linked: {unlinked}")

if unlinked == 0:
    print()
    print("✅ ALL 2012 receipts are now linked to verified banking transactions!")

conn.close()
