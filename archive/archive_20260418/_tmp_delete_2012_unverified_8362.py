"""
Delete 149 unverified 8362 rows from 2012 that duplicate 1615 transactions.
"""
import psycopg2

DRY_RUN = False

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata',
                        user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Find 2012 unverified 8362 rows that match 1615
cur.execute("""
  SELECT bt8.transaction_id, bt8.transaction_date, bt8.debit_amount, bt8.credit_amount,
         bt8.description, bt8.verified, bt8.source_file, bt8.import_batch
  FROM banking_transactions bt8
  WHERE bt8.account_number='0228362'
  AND EXTRACT(YEAR FROM bt8.transaction_date)=2012
  AND bt8.verified=FALSE
  AND EXISTS (
    SELECT 1 FROM banking_transactions bt1
    WHERE bt1.account_number='1615'
    AND bt1.transaction_date = bt8.transaction_date
    AND COALESCE(bt1.debit_amount,0) = COALESCE(bt8.debit_amount,0)
    AND COALESCE(bt1.credit_amount,0) = COALESCE(bt8.credit_amount,0)
  )
  ORDER BY bt8.transaction_date, bt8.transaction_id
""")
rows_to_delete = cur.fetchall()
print(f"Found {len(rows_to_delete)} unverified 2012 8362 rows matching 1615\n")

# Show grouped by batch
from collections import defaultdict
by_batch = defaultdict(list)
for r in rows_to_delete:
    batch = r[7] or r[6] or 'unknown'
    by_batch[batch].append(r)

print("By batch/source:")
for batch, rows in sorted(by_batch.items()):
    print(f"  {batch}: {len(rows)} rows")

print(f"\nSample rows to delete:")
for r in rows_to_delete[:10]:
    tid, d, debit, credit, desc, ver, src, batch = r
    print(f"  {d}  debit={float(debit) if debit else 0:>8.2f}  credit={float(credit) if credit else 0:>8.2f}  "
          f"{(desc or '')[:40]}")

if len(rows_to_delete) > 10:
    print(f"  ... and {len(rows_to_delete) - 10} more")

if DRY_RUN:
    print(f"\n[DRY RUN] Would delete {len(rows_to_delete)} rows")
else:
    to_delete_ids = [r[0] for r in rows_to_delete]
    
    # First, delete any receipt_banking_links pointing to these transactions
    cur.execute("""
        DELETE FROM receipt_banking_links
        WHERE transaction_id = ANY(%s)
    """, (to_delete_ids,))
    links_deleted = cur.rowcount
    print(f"Deleted {links_deleted} receipt_banking_links first")
    
    # Then delete the banking transactions
    cur.execute("""
        DELETE FROM banking_transactions
        WHERE transaction_id = ANY(%s)
        AND account_number='0228362'
    """, (to_delete_ids,))
    deleted = cur.rowcount
    conn.commit()
    print(f"✓ Deleted {deleted} unverified 2012 8362 rows")

conn.close()
