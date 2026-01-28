#!/usr/bin/env python
import psycopg2, os

conn = psycopg2.connect(host=os.environ.get('DB_HOST','localhost'), database=os.environ.get('DB_NAME','almsdata'), user=os.environ.get('DB_USER','postgres'), password=os.environ.get('DB_PASSWORD','***REMOVED***'))
cur = conn.cursor()

print('=== Receipts by source_system ===')
cur.execute("SELECT COALESCE(source_system,'(null)'), COUNT(*) FROM receipts GROUP BY source_system ORDER BY 2 DESC")
for r in cur.fetchall():
    print(r)

print('\n=== Receipts by receipt_source ===')
cur.execute("SELECT COALESCE(receipt_source,'(null)'), COUNT(*) FROM receipts GROUP BY receipt_source ORDER BY 2 DESC")
for r in cur.fetchall():
    print(r)

print('\n=== Receipts with banking link ===')
cur.execute("SELECT COUNT(*) FROM receipts WHERE banking_transaction_id IS NOT NULL OR created_from_banking = TRUE OR is_verified_banking = TRUE")
print('linked count:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM receipts WHERE (banking_transaction_id IS NULL AND (created_from_banking IS NOT TRUE) AND (is_verified_banking IS NOT TRUE))")
print('unlinked count:', cur.fetchone()[0])

print('\n=== Receipts suspected QuickBooks-only ===')
cur.execute("SELECT COUNT(*) FROM receipts WHERE (source_system='QuickBooks' OR receipt_source ILIKE '%quickbooks%') AND (banking_transaction_id IS NULL) AND (COALESCE(created_from_banking, FALSE) = FALSE) AND (COALESCE(is_verified_banking, FALSE) = FALSE)")
print('suspect count:', cur.fetchone()[0])

cur.close(); conn.close()
