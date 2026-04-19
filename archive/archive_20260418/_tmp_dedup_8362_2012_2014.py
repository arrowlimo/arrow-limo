"""
Dry-run deduplication of banking_transactions for account 0228362, years 2012-2014.
Rules:
  - Composite key: transaction_date, posted_date, description, debit_amount, credit_amount, check_number
  - Keep lowest transaction_id per group
  - SKIP rows where is_transfer=true OR is_nsf_charge=true
  - Only years 2012-2014

Set DRY_RUN = False to actually delete.
"""
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal

DRY_RUN = False

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata',
                        user='postgres', password='ArrowLimousine')
cur = conn.cursor(cursor_factory=RealDictCursor)

# Find duplicate groups
cur.execute("""
    WITH eligible AS (
        SELECT transaction_id, transaction_date,
               COALESCE(posted_date::text,'') posted_date,
               COALESCE(description,'') description,
               COALESCE(debit_amount,0) debit_amount,
               COALESCE(credit_amount,0) credit_amount,
               COALESCE(check_number,'') check_number,
               receipt_id, reconciled_receipt_id,
               source_file, import_batch
        FROM banking_transactions
        WHERE account_number = '0228362'
          AND COALESCE(is_transfer, false) = false
          AND COALESCE(is_nsf_charge, false) = false
          AND EXTRACT(YEAR FROM transaction_date) BETWEEN 2012 AND 2014
    ),
    groups AS (
        SELECT transaction_date, posted_date, description,
               debit_amount, credit_amount, check_number,
               MIN(transaction_id) AS keep_id,
               COUNT(*) AS cnt
        FROM eligible
        GROUP BY transaction_date, posted_date, description,
                 debit_amount, credit_amount, check_number
        HAVING COUNT(*) > 1
    ),
    to_delete AS (
        SELECT e.transaction_id, e.transaction_date, e.description,
               e.debit_amount, e.credit_amount, e.check_number,
               e.receipt_id, e.reconciled_receipt_id,
               e.source_file, e.import_batch,
               g.keep_id, g.cnt
        FROM eligible e
        JOIN groups g ON
            g.transaction_date = e.transaction_date AND
            g.posted_date = e.posted_date AND
            g.description = e.description AND
            g.debit_amount = e.debit_amount AND
            g.credit_amount = e.credit_amount AND
            g.check_number = e.check_number
        WHERE e.transaction_id <> g.keep_id
    )
    SELECT * FROM to_delete ORDER BY transaction_date, description, transaction_id
""")

rows = cur.fetchall()

linked   = [r for r in rows if r['receipt_id'] or r['reconciled_receipt_id']]
unlinked = [r for r in rows if not r['receipt_id'] and not r['reconciled_receipt_id']]

print("=" * 90)
print(f"DEDUP DRY-RUN: account 0228362, years 2012-2014  (DRY_RUN={DRY_RUN})")
print("=" * 90)
print(f"\nTotal duplicate rows to remove : {len(rows)}")
print(f"  - Unlinked (safe to delete)  : {len(unlinked)}")
print(f"  - Linked to receipt (review) : {len(linked)}\n")

if linked:
    print("!! LINKED ROWS (need manual review before deleting) !!")
    for r in linked:
        print(f"  txn_id={r['transaction_id']}  {r['transaction_date']}  "
              f"${r['debit_amount']:>10}  {r['description'][:50]}"
              f"  receipt_id={r['receipt_id']}  recon_id={r['reconciled_receipt_id']}")
    print()

print("UNLINKED ROWS TO DELETE:")
debit_total = Decimal('0.00')
credit_total = Decimal('0.00')
for r in unlinked:
    debit_total  += Decimal(str(r['debit_amount']  or 0))
    credit_total += Decimal(str(r['credit_amount'] or 0))
    print(f"  txn_id={r['transaction_id']}  {r['transaction_date']}  "
          f"debit=${r['debit_amount']:>10}  credit=${r['credit_amount']:>8}  "
          f"{r['description'][:45]:45}  src={r['source_file'] or r['import_batch'] or ''}")

print(f"\n  Total debit removed : ${debit_total:>12}")
print(f"  Total credit removed: ${credit_total:>12}")

if not DRY_RUN:
    if not unlinked:
        print("\nNothing to delete.")
    else:
        # Before deleting, re-point any receipt_banking_links from a dup row to the keeper
        relinked = 0
        for r in unlinked:
            cur.execute("""
                UPDATE receipt_banking_links
                SET transaction_id = %s
                WHERE transaction_id = %s
            """, (r['keep_id'], r['transaction_id']))
            if cur.rowcount:
                print(f"  Re-linked receipt_banking_links: txn {r['transaction_id']} -> {r['keep_id']} ({cur.rowcount} rows)")
                relinked += cur.rowcount

        ids_to_delete = [r['transaction_id'] for r in unlinked]
        cur.execute("DELETE FROM banking_transactions WHERE transaction_id = ANY(%s)",
                    (ids_to_delete,))
        deleted = cur.rowcount
        conn.commit()
        print(f"\nDeleted {deleted} rows from banking_transactions.")
        if relinked:
            print(f"Re-linked {relinked} receipt_banking_links to keeper rows.")
        print("Committed.")
else:
    print("\n[DRY RUN] No changes made. Set DRY_RUN=False to apply.")

cur.close()
conn.close()
