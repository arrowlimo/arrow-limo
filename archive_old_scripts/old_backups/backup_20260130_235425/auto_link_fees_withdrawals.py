#!/usr/bin/env python
"""Auto-create receipts for unlinked banking transactions (Bank Fees, Cash Withdrawals).
Excludes source_file = '2014-2017 CIBC 8362.xlsx'.
- Bank Fees -> GL 5400, vendor 'BANK FEES'
- Cash Withdrawal -> GL 3650, vendor 'CASH WITHDRAWAL'
Links banking_transactions.receipt_id and marks reconciliation_status='reconciled'.
"""
import psycopg2
import os
from datetime import datetime

DB_HOST=os.environ.get("DB_HOST","localhost")
DB_NAME=os.environ.get("DB_NAME","almsdata")
DB_USER=os.environ.get("DB_USER","postgres")
DB_PASSWORD=os.environ.get("DB_PASSWORD",os.environ.get("DB_PASSWORD"))

targets=[
    {"category":"Bank Fees","gl":"5400","vendor":"BANK FEES"},
    {"category":"Cash Withdrawal","gl":"3650","vendor":"CASH WITHDRAWAL"},
]

conn=psycopg2.connect(host=DB_HOST,database=DB_NAME,user=DB_USER,password=DB_PASSWORD)
cur=conn.cursor()

print("\n"+"="*80)
print("AUTO LINK BANK FEES & CASH WITHDRAWALS")
print("="*80)

created_total=0
for t in targets:
    cat=t["category"]
    gl=t["gl"]
    vendor=t["vendor"]
    cur.execute("""
        SELECT transaction_id, transaction_date, description,
               COALESCE(debit_amount,0) as d, COALESCE(credit_amount,0) as c, source_file
        FROM banking_transactions
        WHERE receipt_id IS NULL
          AND reconciled_receipt_id IS NULL
          AND reconciled_payment_id IS NULL
          AND reconciled_charter_id IS NULL
          AND category = %s
          AND COALESCE(source_file,'') <> '2014-2017 CIBC 8362.xlsx'
    """, (cat,))
    rows=cur.fetchall()
    print(f"{cat}: {len(rows)} to create/link")
    created=0
    for tid, tdate, desc, d, c, source_file in rows:
        amount = d if d>0 else ( -c if c>0 else 0)
        cur.execute(
            """
            INSERT INTO receipts (
                receipt_date, vendor_name, description, gross_amount,
                gl_account_code, source_system, source_file,
                created_from_banking, banking_transaction_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,true,%s)
            RETURNING receipt_id
            """,
            (tdate, vendor, desc, amount, gl, 'AUTO_BANK_LINK', source_file, tid)
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
    created_total+=created
    print(f"  -> created/linked {created}")

conn.commit()
print(f"\n✅ Total created/linked: {created_total}")
cur.close(); conn.close()
