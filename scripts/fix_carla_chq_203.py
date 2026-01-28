#!/usr/bin/env python3
"""
Fix Carla Metuier CHQ 203 receipt link.
- Update Receipt 139332 from TX 81373 (QB duplicate) to TX 56865 (real bank transaction)
- Mark TX 81373 as QB_DUPLICATE
"""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("=" * 80)
print("FIXING CARLA METUIER CHQ 203")
print("=" * 80)
print()

# 1. Update receipt link from TX 81373 to TX 56865
print("1. Updating Receipt 139332: TX 81373 → TX 56865 (real bank transaction)")
cur.execute("""
    UPDATE receipts
    SET banking_transaction_id = 56865
    WHERE receipt_id = 139332
""")
print(f"   ✅ Updated {cur.rowcount} receipt")

# 2. Mark TX 81373 as QB duplicate
print("2. Marking TX 81373 as QB_DUPLICATE")
cur.execute("""
    UPDATE banking_transactions
    SET reconciliation_status = 'QB_DUPLICATE',
        reconciliation_notes = 'QB import duplicate of TX 56865 (real CIBC bank DEBIT cheque 203)'
    WHERE transaction_id = 81373
""")
print(f"   ✅ Marked {cur.rowcount} transaction as duplicate")

# Commit changes
conn.commit()
print()
print("✅ ALL CHANGES COMMITTED")

# Verify
print()
print("=" * 80)
print("VERIFICATION:")
print("=" * 80)

cur.execute("""
    SELECT receipt_id, banking_transaction_id
    FROM receipts
    WHERE receipt_id = 139332
""")
r_id, bt_id = cur.fetchone()
print(f"\nReceipt {r_id} now linked to TX {bt_id}")

print("\nRelated transactions:")
cur.execute("""
    SELECT transaction_id, description, reconciliation_status
    FROM banking_transactions
    WHERE transaction_id IN (56865, 81373)
    ORDER BY transaction_id
""")
for tx_id, desc, status in cur.fetchall():
    status_display = status if status else "ACTIVE"
    print(f"  TX {tx_id} | {desc[:50]:<50} | {status_display}")

print()
print("✅ CHQ 203 FIX COMPLETE!")
print("   Receipt 139332 now linked to TX 56865 (real CIBC bank transaction)")
print("   TX 81373 marked as QB_DUPLICATE")

cur.close()
conn.close()
