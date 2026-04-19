"""
Detailed breakdown of 143 unlinked 2012 txns for account 1615.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', port=5432, dbname='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

ACCT = '1615'

# Categorize unlinked txns
cur.execute("""
    SELECT
        transaction_date, debit_amount, credit_amount, description, transaction_id,
        reconciliation_status, is_transfer
    FROM banking_transactions
    WHERE account_number=%s
    AND transaction_date >= '2012-01-01' AND transaction_date < '2013-01-01'
    AND NOT EXISTS (
        SELECT 1 FROM receipt_banking_links rbl WHERE rbl.transaction_id = transaction_id
    )
    ORDER BY transaction_date
""", (ACCT,))
rows = cur.fetchall()

deposits = []
debits = []
for r in rows:
    txn_date, debit, credit, desc, tid, rec_status, is_transfer = r
    if credit and not debit:
        deposits.append(r)
    else:
        debits.append(r)

print(f"Total unlinked: {len(rows)}")
print(f"  CREDITS (income/deposits, no receipt needed): {len(deposits)}")
print(f"  DEBITS (expenses, may need receipts): {len(debits)}")

print("\n--- UNLINKED DEBITS (potential missing receipt links) ---")
for r in debits:
    txn_date, debit, credit, desc, tid, rec_status, is_transfer = r
    print(f"  {txn_date}  ${debit or 0:.2f}  [{rec_status}]  is_transfer={is_transfer}  {desc[:70] if desc else ''}  id={tid}")

print("\n--- UNLINKED CREDITS (income - probably fine) ---")
for r in deposits[:20]:
    txn_date, debit, credit, desc, tid, rec_status, is_transfer = r
    print(f"  {txn_date}  +${credit or 0:.2f}  [{rec_status}]  {desc[:60] if desc else ''}  id={tid}")
if len(deposits) > 20:
    print(f"  ... ({len(deposits)-20} more deposits)")

conn.close()
