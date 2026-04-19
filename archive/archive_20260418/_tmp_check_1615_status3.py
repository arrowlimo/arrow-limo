"""
Check current state of receipt_banking_links for CIBC 1615 (account_number='1615'), 2012.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

ACCT = '1615'

# How many 2012 banking transactions exist for 1615
cur.execute("""
    SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions
    WHERE account_number=%s
    AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
""", (ACCT,))
row = cur.fetchone()
print(f"2012 banking txns (1615): count={row[0]}, debits={row[1]}, credits={row[2]}")

# How many are linked to receipts via receipt_banking_links
cur.execute("""
    SELECT COUNT(DISTINCT bt.transaction_id)
    FROM banking_transactions bt
    JOIN receipt_banking_links rbl ON rbl.transaction_id = bt.transaction_id
    WHERE bt.account_number=%s
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
""", (ACCT,))
print(f"2012 txns with receipt_banking_links: {cur.fetchone()[0]}")

# How many unlinked 2012 banking txns for 1615
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions bt
    WHERE bt.account_number=%s
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
    AND NOT EXISTS (
        SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id = bt.transaction_id
    )
""", (ACCT,))
unlinked_bt = cur.fetchone()[0]
print(f"2012 unlinked banking txns (1615): {unlinked_bt}")

# Sample unlinked txns
cur.execute("""
    SELECT bt.transaction_id, bt.transaction_date, bt.debit_amount, bt.description
    FROM banking_transactions bt
    WHERE bt.account_number=%s
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
    AND NOT EXISTS (
        SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id = bt.transaction_id
    )
    ORDER BY bt.transaction_date
    LIMIT 20
""", (ACCT,))
print("Sample unlinked 2012 txns (1615):")
for r in cur.fetchall():
    print(f"  {r[1]} debit={r[2]} desc={r[3][:60] if r[3] else ''}  id={r[0]}")

# How many 2012 receipts are linked to 1615 transactions
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id), SUM(rbl.linked_amount)
    FROM receipts r
    JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
    JOIN banking_transactions bt ON bt.transaction_id = rbl.transaction_id
    WHERE bt.account_number=%s
    AND r.receipt_date >= '2012-01-01' AND r.receipt_date < '2013-01-01'
""", (ACCT,))
row = cur.fetchone()
print(f"\n2012 receipts linked to 1615 banking: count={row[0]}, total_linked={row[1]}")

# Link dates for 1615 2012 links
cur.execute("""
    SELECT rbl.linked_at::date, COUNT(*)
    FROM receipt_banking_links rbl
    JOIN banking_transactions bt ON bt.transaction_id = rbl.transaction_id
    WHERE bt.account_number=%s
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
    GROUP BY rbl.linked_at::date
    ORDER BY rbl.linked_at::date DESC
    LIMIT 10
""", (ACCT,))
print("Link dates (most recent first):")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} links")

conn.close()
