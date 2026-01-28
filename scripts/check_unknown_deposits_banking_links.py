import psycopg2

VENDORS = ['UNKNOWN PAYEE','DEPOSIT','DEPOSIT #X']

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='***REMOVED***')
cur = conn.cursor()

print("Banking linkage summary for UNKNOWN PAYEE / DEPOSIT / DEPOSIT #X:")
cur.execute(
    """
    SELECT vendor_name,
           COUNT(*) AS total,
           SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_count,
           SUM(CASE WHEN banking_transaction_id IS NOT NULL THEN gross_amount ELSE 0 END) AS linked_amount,
           SUM(gross_amount) AS total_amount
    FROM receipts
    WHERE vendor_name = ANY(%s)
    GROUP BY vendor_name
    ORDER BY SUM(gross_amount) DESC
    """,
    (VENDORS,),
)
rows = cur.fetchall()
print(f"{'Vendor':<15} {'Total':>6} {'Linked':>7} {'Linked $':>14} {'Total $':>14}")
print('-'*70)
for r in rows:
    vendor, total, linked, linked_amt, total_amt = r
    print(f"{vendor[:14]:<15} {total:>6} {linked:>7} ${linked_amt:>13,.2f} ${total_amt:>13,.2f}")

print("\nMost recent 10 linked receipts (if any):")
cur.execute(
    """
    SELECT vendor_name, receipt_id, receipt_date, gross_amount, banking_transaction_id
    FROM receipts
    WHERE vendor_name = ANY(%s)
      AND banking_transaction_id IS NOT NULL
    ORDER BY receipt_date DESC
    LIMIT 10
    """,
    (VENDORS,),
)
rows = cur.fetchall()
if not rows:
    print("  None linked to banking")
else:
    print(f"{'Vendor':<15} {'ID':<8} {'Date':<12} {'Amount':>12} {'BankTxnID':<12}")
    for r in rows:
        vendor, rid, date, amt, btid = r
        print(f"{vendor[:14]:<15} {rid:<8} {str(date):<12} ${amt:>11,.2f} {btid}")

conn.close()
