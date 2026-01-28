#!/usr/bin/env python
"""Check for GL 9999 duplicates of already-matched banking transactions."""

import psycopg2
import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_NAME = os.environ.get("DB_NAME", "almsdata")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("DB_PASSWORD"))

conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD)
cur = conn.cursor()

print("\n" + "="*100)
print("GL 9999 DUPLICATE CHECK - Are these already matched to banking?")
print("="*100)

# 1. Check if any GL 9999 already have banking_transaction_id set
print("\n1️⃣  GL 9999 entries already linked to banking_transaction_id:")
cur.execute("""
    SELECT COUNT(*), COUNT(DISTINCT banking_transaction_id)
    FROM receipts
    WHERE gl_account_code = '9999' AND banking_transaction_id IS NOT NULL
""")

count_linked, count_distinct = cur.fetchone()
print(f"   {count_linked} GL 9999 entries have banking_transaction_id set")
print(f"   {count_distinct} distinct banking transactions")

if count_linked > 0:
    print(f"\n   These should probably be deleted (already matched):")
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.receipt_date, 
               bt.transaction_date, bt.description
        FROM receipts r
        JOIN banking_transactions bt ON r.banking_transaction_id = bt.transaction_id
        WHERE r.gl_account_code = '9999'
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        print(f"   Receipt {row[0]:<8} {row[1]:<30} ${row[2]:>10.2f} → Banking: {row[5][:40]}")

# 2. Check for GL 9999 duplicates by amount + date within same account
print(f"\n2️⃣  GL 9999 potential duplicates (same amount + date, 2+ occurrences):")

cur.execute("""
    SELECT gross_amount, receipt_date, COUNT(*) as cnt, 
           STRING_AGG(vendor_name, ', ' ORDER BY vendor_name) as vendors
    FROM receipts
    WHERE gl_account_code = '9999'
    GROUP BY gross_amount, receipt_date
    HAVING COUNT(*) >= 2
    ORDER BY cnt DESC
    LIMIT 15
""")

dup_count = 0
for row in cur.fetchall():
    amount, date, count, vendors = row
    print(f"   ${amount:>10.2f} on {date}: {count} entries | Vendors: {vendors[:60]}")
    dup_count += count

print(f"\n   Total GL 9999 entries appearing in duplicate groups: {dup_count}")

# 3. Cross-check: GL 9999 amounts that match reconciled banking but different vendor
print(f"\n3️⃣  GL 9999 entries matching banking by amount but with different vendor name:")

cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    WHERE r.gl_account_code = '9999'
    AND EXISTS (
        SELECT 1 FROM banking_transactions bt
        WHERE (bt.debit_amount = r.gross_amount OR bt.credit_amount = r.gross_amount)
        AND bt.transaction_date = r.receipt_date
        AND bt.reconciliation_status = 'reconciled'
    )
""")

count_matches = cur.fetchone()[0]
print(f"   {count_matches} GL 9999 entries match reconciled banking by amount+date")

if count_matches > 0:
    print(f"\n   Sample matches (GL 9999 duplicating reconciled banking):")
    cur.execute("""
        SELECT r.receipt_id, r.vendor_name, r.gross_amount, r.receipt_date,
               bt.description, bt.reconciliation_status
        FROM receipts r
        JOIN banking_transactions bt ON 
            (bt.debit_amount = r.gross_amount OR bt.credit_amount = r.gross_amount)
            AND bt.transaction_date = r.receipt_date
        WHERE r.gl_account_code = '9999'
        AND bt.reconciliation_status = 'reconciled'
        LIMIT 10
    """)
    
    for row in cur.fetchall():
        print(f"   Receipt {row[0]:<8} {row[1]:<30} ${row[2]:>10.2f} | Banking: {row[4][:35]}")

cur.close()
conn.close()

print("\n" + "="*100)
print("SUMMARY: If any GL 9999 entries have banking_transaction_id or match reconciled")
print("         banking transactions, they may be duplicates and should be deleted.")
print("="*100)
