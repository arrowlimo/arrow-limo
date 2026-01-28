#!/usr/bin/env python3
"""Backup and delete all 2012 CIBC 0228362 banking data (auto-generated receipts)."""

import os
import psycopg2
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REMOVED***")
)
cur = conn.cursor()

print("=" * 100)
print("BACKUP AND DELETE 2012 CIBC 0228362 DATA")
print("=" * 100 + "\n")

# Step 1: Backup banking transactions
print("STEP 1: Backing up banking transactions...")
cur.execute("""
    SELECT * FROM banking_transactions
    WHERE account_number = '0228362'
    AND EXTRACT(YEAR FROM transaction_date) = 2012
    ORDER BY transaction_id
""")

bt_cols = [d[0] for d in cur.description]
bt_rows = cur.fetchall()

backup_data = {
    'banking_transactions': {
        'columns': bt_cols,
        'data': [dict(zip(bt_cols, row)) for row in bt_rows]
    }
}

print(f"  Backed up {len(bt_rows)} banking transactions")

# Step 2: Backup auto-generated receipts linked to these transactions
print("\nSTEP 2: Backing up auto-generated receipts...")
cur.execute("""
    SELECT r.* FROM receipts r
    WHERE r.banking_transaction_id IN (
        SELECT transaction_id FROM banking_transactions
        WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    )
    AND r.created_from_banking = TRUE
    ORDER BY r.receipt_id
""")

r_cols = [d[0] for d in cur.description]
r_rows = cur.fetchall()

backup_data['receipts'] = {
    'columns': r_cols,
    'data': [dict(zip(r_cols, row)) for row in r_rows]
}

print(f"  Backed up {len(r_rows)} auto-generated receipts")

# Write backup to file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_file = f"l:\\limo\\almsdata_backup_2012_CIBC_0228362_{timestamp}.json"

with open(backup_file, 'w') as f:
    # Convert dates and decimals to strings for JSON
    backup_json = json.dumps(backup_data, default=str, indent=2)
    f.write(backup_json)

print(f"\n✅ Backup saved to: {backup_file}")

# Step 3: Delete the data
print("\n" + "=" * 100)
print("STEP 3: Deleting data (user confirmation required)")
print("=" * 100)
print(f"\nAbout to delete:")
print(f"  • {len(bt_rows)} banking transactions (2012, account 0228362)")
print(f"  • {len(r_rows)} auto-generated receipts")
print(f"\nBackup file: {backup_file}")

user_confirm = input("\nType 'DELETE' to confirm deletion: ").strip().upper()

if user_confirm == "DELETE":
    print("\n⚠️  DELETING DATA...\n")
    
    # Delete auto-generated receipts first
    cur.execute("""
        DELETE FROM receipts
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
        )
        AND created_from_banking = TRUE
    """)
    
    deleted_receipts = cur.rowcount
    print(f"✅ Deleted {deleted_receipts} auto-generated receipts")
    
    conn.commit()
    
    # Delete banking transactions
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    deleted_transactions = cur.rowcount
    print(f"✅ Deleted {deleted_transactions} banking transactions")
    
    conn.commit()
    
    # Verify deletion
    cur.execute("""
        SELECT COUNT(*) FROM banking_transactions
        WHERE account_number = '0228362'
        AND EXTRACT(YEAR FROM transaction_date) = 2012
    """)
    
    remaining = cur.fetchone()[0]
    
    if remaining == 0:
        print("\n" + "=" * 100)
        print("✅ DELETION COMPLETE")
        print("=" * 100)
        print(f"\nDeleted:")
        print(f"  • {deleted_transactions} banking transactions")
        print(f"  • {deleted_receipts} auto-generated receipts")
        print(f"\nBackup location: {backup_file}")
    else:
        print(f"\n❌ ERROR: {remaining} transactions still remain")
        conn.rollback()
else:
    print("\n❌ Deletion cancelled - no data was deleted")
    conn.rollback()

cur.close()
conn.close()
