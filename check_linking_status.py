import psycopg2
conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("\n" + "=" * 100)
print("CURRENT LINKING STATUS")
print("=" * 100)

# Receipts
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(banking_transaction_id) as with_banking,
        COUNT(CASE WHEN banking_transaction_id IS NULL THEN 1 END) as without_banking
    FROM receipts
""")
total_r, with_bank, without_bank = cur.fetchone()
print(f'\nRECEIPTS:')
print(f'  Total:           {total_r:8d}')
print(f'  Linked to bank:  {with_bank:8d} ({with_bank*100//total_r}%)')
print(f'  Without link:    {without_bank:8d} ({without_bank*100//total_r}%)')

# Banking transactions
cur.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(reconciled_payment_id) as to_payments,
        COUNT(reconciled_receipt_id) as to_receipts,
        COUNT(CASE WHEN reconciled_payment_id IS NULL AND reconciled_receipt_id IS NULL THEN 1 END) as unlinked
    FROM banking_transactions
""")
total_b, to_pays, to_recs, unlinked = cur.fetchone()
print(f'\nBANKING TRANSACTIONS:')
print(f'  Total:               {total_b:8d}')
print(f'  Linked to payments:  {to_pays:8d} ({to_pays*100//total_b}%)')
print(f'  Linked to receipts:  {to_recs:8d} ({to_recs*100//total_b}%)')
print(f'  Unlinked:            {unlinked:8d} ({unlinked*100//total_b}%)')

# Calculate completion
linked_total = to_pays + to_recs
completion = linked_total * 100 // total_b
print(f'\n  OVERALL COMPLETION:  {linked_total:8d}/{total_b} ({completion}%)')

print("\n" + "=" * 100 + "\n")

cur.close()
conn.close()
