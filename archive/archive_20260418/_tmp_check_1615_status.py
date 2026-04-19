"""
Check current state of receipt_banking_links for CIBC 1615 (bank_id=4), 2012.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# How many 2012 banking transactions exist for bank_id=4
cur.execute("""
    SELECT COUNT(*), SUM(debit_amount), SUM(credit_amount)
    FROM banking_transactions
    WHERE bank_account_id=4
    AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
""")
row = cur.fetchone()
print(f"2012 banking txns (bank_id=4): count={row[0]}, debits={row[1]}, credits={row[2]}")

# How many are linked to receipts
cur.execute("""
    SELECT COUNT(DISTINCT bt.transaction_id)
    FROM banking_transactions bt
    JOIN receipt_banking_links rbl ON rbl.transaction_id = bt.transaction_id
    WHERE bt.bank_account_id=4
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
""")
print(f"2012 txns with receipt_banking_links: {cur.fetchone()[0]}")

# How many 2012 receipts are linked to bank_id=4 transactions
cur.execute("""
    SELECT COUNT(DISTINCT r.receipt_id), SUM(rbl.linked_amount)
    FROM receipts r
    JOIN receipt_banking_links rbl ON rbl.receipt_id = r.receipt_id
    JOIN banking_transactions bt ON bt.transaction_id = rbl.transaction_id
    WHERE bt.bank_account_id=4
    AND r.receipt_date >= '2012-01-01' AND r.receipt_date < '2013-01-01'
""")
row = cur.fetchone()
print(f"2012 receipts linked to 1615 banking: count={row[0]}, total_linked={row[1]}")

# How many 2012 receipts have NO banking link at all
cur.execute("""
    SELECT COUNT(*)
    FROM receipts r
    WHERE r.receipt_date >= '2012-01-01' AND r.receipt_date < '2013-01-01'
    AND NOT EXISTS (
        SELECT 1 FROM receipt_banking_links rbl WHERE rbl.receipt_id = r.receipt_id
    )
""")
print(f"2012 receipts with NO banking link: {cur.fetchone()[0]}")

# Unlinked 2012 banking transactions for bank 1615
cur.execute("""
    SELECT COUNT(*)
    FROM banking_transactions bt
    WHERE bt.bank_account_id=4
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
    AND NOT EXISTS (
        SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id = bt.transaction_id
    )
""")
print(f"2012 unlinked banking txns (1615): {cur.fetchone()[0]}")

# Check if find_1615_gaps.py was run (i.e., look at recent receipt_banking_links for 2012 1615 txns)
cur.execute("""
    SELECT rbl.linked_at::date, COUNT(*)
    FROM receipt_banking_links rbl
    JOIN banking_transactions bt ON bt.transaction_id = rbl.transaction_id
    WHERE bt.bank_account_id=4
    AND bt.transaction_date >= '2012-01-01' AND bt.transaction_date < '2013-01-01'
    GROUP BY rbl.linked_at::date
    ORDER BY rbl.linked_at::date DESC
    LIMIT 10
""")
print("Link dates (most recent first):")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} links")

conn.close()
