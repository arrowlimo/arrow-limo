#!/usr/bin/env python
"""Auto-create receipts for ALL remaining unlinked banking transactions.
Processes all categories, all source_files (including 2014-2017 CIBC 8362.xlsx).
- Sets gl_account_code = NULL for unknown/mixed categories
- Uses vendor_extracted/vendor_truncated/description for vendor_name
- Links banking_transactions.receipt_id and marks reconciliation_status='reconciled'
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*100)
print("AUTO LINK ALL REMAINING BANKING TRANSACTIONS")
print("="*100)

# Get count first
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
""")
total_count=cur.fetchone()[0]
print(f"Total unlinked banking transactions: {total_count}")

# Fetch all unlinked banking transactions
cur.execute("""
    SELECT transaction_id, transaction_date, description, category,
           COALESCE(debit_amount,0) as d, COALESCE(credit_amount,0) as c,
           vendor_extracted, vendor_truncated, source_file
    FROM banking_transactions
    WHERE receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
    ORDER BY transaction_date, transaction_id
""")
rows=cur.fetchall()
print(f"Fetched {len(rows)} rows to process\n")

created=0
batch_size=1000
for idx, (tid, tdate, desc, cat, d, c, vend_ex, vend_tr, src_file) in enumerate(rows, 1):
    # Determine amount (credit for income, debit for expense)
    amount = c if c > 0 else (d if d > 0 else 0)
    if c > 0 and d > 0:  # both present, use net
        amount = c - d
    
    # Determine vendor
    vendor = vend_ex or vend_tr or (desc[:50] if desc else (cat or 'UNKNOWN'))
    
    # Insert receipt
    cur.execute(
        """
        INSERT INTO receipts (
            receipt_date, vendor_name, description, gross_amount,
            gl_account_code, source_system, source_file, category,
            created_from_banking, banking_transaction_id
        )
        VALUES (%s,%s,%s,%s,NULL,%s,%s,%s,true,%s)
        RETURNING receipt_id
        """,
        (tdate, vendor, desc, amount, 'AUTO_BANK_LINK', src_file, cat, tid)
    )
    rid=cur.fetchone()[0]
    
    # Link banking transaction
    cur.execute(
        """
        UPDATE banking_transactions
        SET receipt_id=%s, reconciliation_status='reconciled', reconciled_at=NOW()
        WHERE transaction_id=%s
        """,
        (rid, tid)
    )
    created+=1
    
    # Commit in batches
    if created % batch_size == 0:
        conn.commit()
        print(f"  Progress: {created}/{total_count} ({100*created/total_count:.1f}%)")

conn.commit()
print(f"\n✅ Total created/linked: {created}")

# Verify
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions
    WHERE receipt_id IS NULL
      AND reconciled_receipt_id IS NULL
      AND reconciled_payment_id IS NULL
      AND reconciled_charter_id IS NULL
""")
remaining=cur.fetchone()[0]
print(f"📊 Remaining unlinked banking transactions: {remaining}")

cur.close(); conn.close()
