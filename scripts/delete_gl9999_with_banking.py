#!/usr/bin/env python
"""Delete GL 9999 receipts that are already linked to banking_transaction_id.
Backs up the entries before deletion.
"""

import psycopg2
import os
import json
from datetime import datetime

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "***REMOVED***")

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*100)
print("DELETE GL 9999 RECEIPTS ALREADY LINKED TO BANKING")
print("="*100)

# Fetch for backup
cur.execute(
    """
    SELECT json_agg(row_to_json(t))
    FROM (
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, gl_account_code,
               banking_transaction_id, created_from_banking, description
        FROM receipts
        WHERE gl_account_code = '9999' AND banking_transaction_id IS NOT NULL
    ) t
    """
)
backup = cur.fetchone()[0]
count_backup = len(backup) if backup else 0

if count_backup == 0:
    print("No GL 9999 entries linked to banking found. Nothing to delete.")
    cur.close()
    conn.close()
    raise SystemExit

os.makedirs("backups", exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = f"backups/gl9999_with_banking_{timestamp}.json"
with open(backup_path, "w", encoding="utf-8") as f:
    json.dump(backup, f, indent=2, default=str)

print(f"Backup created: {backup_path} ({count_backup} entries)")

# Unlink banking_transactions.receipt_id for these receipts to satisfy FK
cur.execute(
    """
    UPDATE banking_transactions
    SET receipt_id = NULL, reconciled_receipt_id = NULL, reconciliation_status = NULL
    WHERE receipt_id IN (
        SELECT receipt_id FROM receipts
        WHERE gl_account_code = '9999' AND banking_transaction_id IS NOT NULL
    )
    """
)
unlinked = cur.rowcount
print(f"Unlinked {unlinked} banking_transactions from duplicate receipts")

# Delete
cur.execute(
    """
    DELETE FROM receipts
    WHERE gl_account_code = '9999' AND banking_transaction_id IS NOT NULL
    """
)
rows_deleted = cur.rowcount
conn.commit()

print(f"\n✅ Deleted {rows_deleted} GL 9999 receipts linked to banking_transaction_id")

# Show remaining GL 9999 count
cur.execute("SELECT COUNT(*) FROM receipts WHERE gl_account_code = '9999'")
remaining = cur.fetchone()[0]
print(f"📊 Remaining GL 9999 entries: {remaining}")

cur.close()
conn.close()
