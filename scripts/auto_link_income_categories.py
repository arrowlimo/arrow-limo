#!/usr/bin/env python
"""Auto-create receipts for unlinked banking income categories (card payments, email transfers, other).
- Categories: Income - Card Payments, Income - Email Transfer, Income - Other
- Uses vendor_extracted/vendor_truncated/description for vendor_name fallback.
- Sets gl_account_code = NULL to avoid misclassification; can be reclassified later.
- Links banking_transactions.receipt_id and marks reconciliation_status='reconciled'.
- Includes all source_files (per user request, including 8362/2014-2017 if present).
"""
import psycopg2
import os

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD","***REMOVED***")

target_categories=["Income - Card Payments", "Income - Email Transfer", "Income - Other"]

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*80)
print("AUTO LINK INCOME CATEGORIES (card/email/other)")
print("="*80)

total_created=0
for cat in target_categories:
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               COALESCE(debit_amount,0) as d, COALESCE(credit_amount,0) as c,
               vendor_extracted, vendor_truncated, source_file
        FROM banking_transactions
        WHERE receipt_id IS NULL
          AND reconciled_receipt_id IS NULL
          AND reconciled_payment_id IS NULL
          AND reconciled_charter_id IS NULL
          AND category = %s
    """, (cat,))
    rows=cur.fetchall()
    print(f"{cat}: {len(rows)} to create/link")
    created=0
    for tid, tdate, desc, d, c, vend_ex, vend_tr, src_file in rows:
        amount = c if c>0 else (-d if d>0 else 0)
        vendor = vend_ex or vend_tr or (desc[:50] if desc else cat)
        cur.execute(
            """
            INSERT INTO receipts (
                receipt_date, vendor_name, description, gross_amount,
                gl_account_code, source_system, source_file,
                created_from_banking, banking_transaction_id
            )
            VALUES (%s,%s,%s,%s,NULL,%s,%s,true,%s)
            RETURNING receipt_id
            """,
            (tdate, vendor, desc, amount, 'AUTO_BANK_LINK', src_file, tid)
        )
        rid=cur.fetchone()[0]
        cur.execute(
            """
            UPDATE banking_transactions
            SET receipt_id=%s, reconciliation_status='reconciled', reconciled_at=NOW()
            WHERE transaction_id=%s
            """,
            (rid, tid)
        )
        created+=1
    total_created+=created
    print(f"  -> created/linked {created}")

conn.commit()
print(f"\n✅ Total created/linked: {total_created}")
cur.close(); conn.close()
