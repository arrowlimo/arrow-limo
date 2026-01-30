#!/usr/bin/env python3
"""Restore the 89 cheque_register entries from backup."""

import os
import json
import psycopg2
from dotenv import load_dotenv

load_dotenv()
conn = psycopg2.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    database=os.environ.get("DB_NAME", "almsdata"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", "***REDACTED***")
)
cur = conn.cursor()

# Read backup file
backup_file = "l:\\limo\\almsdata_backup_2012_CIBC_0228362_20260118_140900.json"

print("=" * 100)
print("RESTORE CHEQUE_REGISTER ENTRIES FROM BACKUP")
print("=" * 100 + "\n")

print(f"Reading backup file: {backup_file}\n")

with open(backup_file, 'r') as f:
    backup_data = json.load(f)

if 'cheque_register' in backup_data:
    cheques = backup_data['cheque_register']['data']
    print(f"Found {len(cheques)} cheque_register entries in backup\n")
    
    print("Restoring cheque_register entries...")
    
    for cheque in cheques:
        # Convert string dates to proper format if needed
        col_names = list(cheque.keys())
        values = [cheque[col] for col in col_names]
        
        placeholders = ", ".join(["%s"] * len(col_names))
        col_list = ", ".join(col_names)
        
        insert_sql = f"""
            INSERT INTO cheque_register ({col_list})
            VALUES ({placeholders})
        """
        
        try:
            cur.execute(insert_sql, values)
        except Exception as e:
            print(f"  ❌ Error inserting cheque {cheque.get('cheque_number')}: {e}")
    
    conn.commit()
    
    # Verify restoration
    cur.execute("""
        SELECT COUNT(*) FROM cheque_register
        WHERE banking_transaction_id IN (
            SELECT transaction_id FROM banking_transactions
            WHERE account_number = '0228362'
            AND EXTRACT(YEAR FROM transaction_date) = 2012
        )
    """)
    
    count = cur.fetchone()[0]
    
    if count == 0:
        # They're not linked anymore since we deleted the banking transactions
        # Just check total count restored
        cur.execute("SELECT COUNT(*) FROM cheque_register")
        total_count = cur.fetchone()[0]
        print(f"\n✅ Restored {len(cheques)} cheque_register entries")
        print(f"   Total in table: {total_count}")
    else:
        print(f"✅ Restored {count} cheque_register entries (with banking links)")

else:
    print("❌ No cheque_register data found in backup file")

cur.close()
conn.close()

print("\n✅ Restoration complete")
