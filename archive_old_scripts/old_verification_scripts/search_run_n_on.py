"""Search for RUN N ON EMPTY receipt"""
import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT', 5432)
    )
    
    cur = conn.cursor()
    
    # Search for RUN N ON EMPTY receipt
    cur.execute("""
        SELECT 
            receipt_id,
            receipt_date,
            vendor_name,
            gross_amount,
            gl_account_code,
            gl_account_name,
            payment_method,
            banking_transaction_id,
            reserve_number,
            description,
            reimbursement_amount
        FROM receipts 
        WHERE vendor_name ILIKE '%RUN N ON%'
        ORDER BY receipt_date DESC
        LIMIT 10;
    """)
    
    receipts = cur.fetchall()
    
    print("RUN N ON EMPTY Receipts:")
    print("=" * 100)
    
    for r in receipts:
        print(f"\nReceipt ID: {r[0]}")
        print(f"  Date: {r[1]}")
        print(f"  Vendor: {r[2]}")
        print(f"  Amount: ${r[3]}")
        print(f"  GL: {r[4]} - {r[5]}")
        print(f"  Payment Method: {r[6]}")
        print(f"  Banking ID: {r[7]}")
        print(f"  Charter: {r[8]}")
        print(f"  Description: {r[9]}")
        print(f"  Reimbursement Amount: {r[10]}")
        print("-" * 100)
    
    if not receipts:
        print("No receipts found for 'RUN N ON EMPTY'")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
