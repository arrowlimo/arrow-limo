"""
Show details of the CHEQUE error receipts.
"""
import psycopg2
import os

conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'almsdata'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', '***REMOVED***')
)
cur = conn.cursor()

# Get details on cheque error receipts
cur.execute("""
    SELECT 
        receipt_id,
        receipt_date,
        vendor_name,
        description,
        gross_amount,
        gl_account_code,
        category,
        banking_transaction_id
    FROM receipts
    WHERE vendor_name LIKE 'CHEQUE%' 
    AND vendor_name NOT LIKE 'CHEQUE (%'
    AND receipt_date >= '2012-01-01'
    ORDER BY receipt_date DESC
""")

print("=== CHEQUE ERROR RECEIPTS ===\n")
for receipt_id, receipt_date, vendor_name, description, gross_amount, gl_code, category, btid in cur.fetchall():
    print(f"Receipt {receipt_id}")
    print(f"  Date: {receipt_date}")
    print(f"  Vendor: {vendor_name}")
    print(f"  Description: {description}")
    print(f"  Amount: ${gross_amount:,.2f}")
    print(f"  GL: {gl_code} | Category: {category}")
    print(f"  Banking TX ID: {btid}")
    print()
    
    # Get banking details if linked
    if btid:
        cur.execute("""
            SELECT transaction_date, description, debit_amount, credit_amount
            FROM banking_transactions
            WHERE transaction_id = %s
        """, (btid,))
        bt = cur.fetchone()
        if bt:
            print(f"  Bank TX: {bt[0]} | {bt[1]}")
            if bt[2]:
                print(f"    Debit: ${bt[2]:,.2f}")
            if bt[3]:
                print(f"    Credit: ${bt[3]:,.2f}")
    print()

cur.close()
conn.close()
