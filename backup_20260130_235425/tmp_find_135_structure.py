import psycopg2

conn = psycopg2.connect(host='localhost', database='almsdata', user='postgres', password='ArrowLimousine')
cur = conn.cursor()

# Find the $135.00 parent receipt
print("Looking for parent receipt of $135.00:\n")

cur.execute("""
    SELECT receipt_id, receipt_date, vendor_name, gross_amount, parent_receipt_id, is_split_receipt, banking_transaction_id
    FROM receipts
    WHERE EXTRACT(YEAR FROM receipt_date) = 2012
        AND vendor_name ILIKE '%RUN''N ON EMPTY%'
        AND gross_amount = 135.00
    ORDER BY receipt_date
""")

parent_rows = cur.fetchall()
for receipt_id, receipt_date, vendor_name, gross_amount, parent_id, is_split, banking_id in parent_rows:
    print(f"ID {receipt_id} | {receipt_date} | {vendor_name} | ${gross_amount:.2f} | Parent: {parent_id} | Split: {is_split} | Banking: {banking_id}")
    
    # If this is a parent, find its children
    if is_split or parent_id is None:
        cur.execute("""
            SELECT receipt_id, receipt_date, gross_amount, banking_transaction_id
            FROM receipts
            WHERE parent_receipt_id = %s
            ORDER BY receipt_id
        """, (receipt_id,))
        
        children = cur.fetchall()
        if children:
            print(f"  Children ({len(children)} total):")
            child_sum = 0
            for child_id, child_date, child_amount, child_banking in children:
                print(f"    - ID {child_id} | {child_date} | ${child_amount:.2f} | Banking: {child_banking}")
                child_sum += float(child_amount)
            print(f"  Children sum: ${child_sum:.2f}")
        print()

# Now find the specific amounts
print("\n" + "=" * 70)
print("Looking for the specific amounts $4.00, $36.01, $94.99:\n")

for amount in [4.00, 36.01, 94.99]:
    cur.execute("""
        SELECT receipt_id, receipt_date, vendor_name, gross_amount, parent_receipt_id, is_split_receipt
        FROM receipts
        WHERE EXTRACT(YEAR FROM receipt_date) = 2012
            AND vendor_name ILIKE '%RUN''N ON EMPTY%'
            AND ABS(gross_amount - %s) < 0.01
        ORDER BY receipt_date
    """, (amount,))
    
    rows = cur.fetchall()
    if rows:
        print(f"\n${amount:.2f} receipts:")
        for receipt_id, receipt_date, vendor_name, gross_amount, parent_id, is_split in rows:
            parent_status = f"[CHILD OF {parent_id}]" if parent_id else "[PARENT]" if is_split else "[STANDALONE]"
            print(f"  ID {receipt_id} | {receipt_date} | ${gross_amount:.2f} {parent_status}")

cur.close()
conn.close()
