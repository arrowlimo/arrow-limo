"""
Delete duplicate banking transactions
Keep the oldest transaction_id for each duplicate group
"""
import psycopg2
import os
from datetime import datetime

conn = psycopg2.connect(
    host='localhost',
    database='almsdata',
    user='postgres',
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()

print("=== BANKING TRANSACTION DUPLICATE REMOVAL ===\n")

# Step 1: Create backup
backup_table = f"banking_transactions_dedup_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
print(f"Creating backup: {backup_table}...")

cur.execute(f"""
    CREATE TABLE {backup_table} AS
    SELECT * FROM banking_transactions
    WHERE account_number = '0228362'
""")
conn.commit()

cur.execute(f"SELECT COUNT(*) FROM {backup_table}")
backup_count = cur.fetchone()[0]
print(f"✓ Backed up {backup_count:,} CIBC transactions\n")

# Step 2: Identify duplicates (keep oldest transaction_id)
print("Identifying duplicates...")

cur.execute("""
    SELECT 
        transaction_date,
        description,
        COALESCE(debit_amount, 0) as debit,
        COALESCE(credit_amount, 0) as credit,
        COUNT(*) as count,
        MIN(transaction_id) as keep_id,
        ARRAY_AGG(transaction_id ORDER BY transaction_id) as all_ids
    FROM banking_transactions
    WHERE account_number = '0228362'
    GROUP BY transaction_date, description, COALESCE(debit_amount, 0), COALESCE(credit_amount, 0)
    HAVING COUNT(*) > 1
    ORDER BY COUNT(*) DESC
""")

duplicate_groups = cur.fetchall()
print(f"Found {len(duplicate_groups)} duplicate groups\n")

# Step 3: Build list of transaction IDs to delete
to_delete = []
delete_summary = []

for group in duplicate_groups:
    date, desc, debit, credit, count, keep_id, all_ids = group
    # Delete all except the first (oldest) ID
    delete_ids = [tid for tid in all_ids if tid != keep_id]
    to_delete.extend(delete_ids)
    
    delete_summary.append({
        'date': date,
        'description': desc[:60],
        'amount': debit if debit > 0 else credit,
        'count': count,
        'keep': keep_id,
        'delete': delete_ids
    })

print(f"Transactions to delete: {len(to_delete)}\n")
print("=== DELETION PREVIEW (Top 20) ===\n")

for i, item in enumerate(delete_summary[:20], 1):
    print(f"{i}. {item['date']} | ${item['amount']:,.2f} | {item['count']} copies")
    print(f"   {item['description']}")
    print(f"   Keep: TX {item['keep']} | Delete: {item['delete']}")
    print()

# Step 4: Execute deletion
if to_delete:
    print(f"\nDeleting {len(to_delete)} duplicate transactions...")
    
    # Delete in batches
    batch_size = 100
    deleted_total = 0
    
    for i in range(0, len(to_delete), batch_size):
        batch = to_delete[i:i+batch_size]
        cur.execute("""
            DELETE FROM banking_transactions
            WHERE transaction_id = ANY(%s)
        """, (batch,))
        deleted_total += cur.rowcount
        
        if (i + batch_size) % 500 == 0:
            print(f"  Deleted {deleted_total}/{len(to_delete)}...")
    
    conn.commit()
    print(f"✓ Deleted {deleted_total} duplicate transactions\n")
    
    # Step 5: Verify
    cur.execute("""
        SELECT COUNT(*)
        FROM (
            SELECT COUNT(*) as count
            FROM banking_transactions
            WHERE account_number = '0228362'
            GROUP BY transaction_date, description, COALESCE(debit_amount, 0), COALESCE(credit_amount, 0)
            HAVING COUNT(*) > 1
        ) subq
    """)
    
    remaining_dups = cur.fetchone()[0]
    
    print("=== VERIFICATION ===")
    print(f"Remaining duplicate groups: {remaining_dups}")
    
    if remaining_dups == 0:
        print("✓ All duplicates removed!")
    else:
        print("⚠️ Some duplicates remain (may need manual review)")
    
    # Final counts
    cur.execute("SELECT COUNT(*) FROM banking_transactions WHERE account_number = '0228362'")
    final_count = cur.fetchone()[0]
    
    print(f"\n=== FINAL SUMMARY ===")
    print(f"Original transactions: {backup_count:,}")
    print(f"Duplicates deleted: {deleted_total:,}")
    print(f"Final transactions: {final_count:,}")
    print(f"Backup table: {backup_table}")

else:
    print("No duplicates to delete!")

cur.close()
conn.close()
