import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

print("=" * 70)
print("Finding the $135 RUN'N ON EMPTY structure")
print("=" * 70 + "\n")

# Find the specific child amounts
amounts = [4.00, 36.01, 94.99]

for amount in amounts:
    cur.execute("""
        SELECT receipt_id, receipt_date, gross_amount, parent_receipt_id
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            AND vendor_name ILIKE '%RUN''N ON EMPTY%'
            AND ABS(gross_amount - %s) < 0.01
    """, (amount,))
    
    result = cur.fetchone()
    if result:
        receipt_id, receipt_date, gross_amount, parent_id = result
        print(f"${amount:.2f} receipt: ID {receipt_id} | {receipt_date} | Parent: {parent_id}")
        
        # If it has a parent, show the parent
        if parent_id:
            cur.execute("""
                SELECT receipt_id, receipt_date, gross_amount, banking_transaction_id
                FROM receipts WHERE receipt_id = %s
            """, (parent_id,))
            parent_result = cur.fetchone()
            if parent_result:
                p_id, p_date, p_amount, p_banking = parent_result
                print(f"    └─ Parent: ID {p_id} | {p_date} | ${p_amount:.2f} | Banking: {p_banking}\n")

cur.close()
conn.close()
