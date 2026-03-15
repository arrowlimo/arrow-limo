import psycopg2
import sys

try:
    conn = psycopg2.connect(host='localhost', user='postgres', password='ArrowLimousine', dbname='almsdata')
    cur = conn.cursor()
    
    # Step 1: Create GL 1135 if needed
    cur.execute("SELECT account_code FROM chart_of_accounts WHERE account_code='1135'")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO chart_of_accounts 
            (account_code, account_name, account_type, parent_account, is_active, is_system)
            VALUES ('1135', 'Prepaid Visa Cards', 'Asset', '1100', TRUE, FALSE)
        """)
        print("Created GL 1135")
    else:
        print("GL 1135 exists")
    
    # Step 2: Check for Money Mart on 09/12/2012
    cur.execute("""
        SELECT receipt_id, gross_amount 
        FROM receipts 
        WHERE vendor_name ILIKE '%money%mart%' AND receipt_date='2012-09-12'
    """)
    existing = cur.fetchall()
    
    if existing:
        print(f"Found {len(existing)} existing - updating to GL 1135")
        for rec_id, amt in existing:
            cur.execute("""
                UPDATE receipts 
                SET gl_account_code='1135', gl_account_name='Prepaid Visa Cards'
                WHERE receipt_id=%s
            """, (rec_id,))
            print(f"  Updated {rec_id}: ${amt}")
    else:
        print("Creating 2 new transactions")
        # Create $900
        cur.execute("""
            INSERT INTO receipts 
            (receipt_date, vendor_name, gross_amount, gl_account_code, gl_account_name,
             payment_method, description, receipt_category)
            VALUES 
            ('2012-09-12', 'Money Mart', 900.00, '1135', 'Prepaid Visa Cards',
             'Cash', 'Prepaid Visa load $900', 'Banking')
            RETURNING receipt_id
        """)
        id1 = cur.fetchone()[0]
        print(f"  Created {id1}: $900")
        
        # Create $750
        cur.execute("""
            INSERT INTO receipts 
            (receipt_date, vendor_name, gross_amount, gl_account_code, gl_account_name,
             payment_method, description, receipt_category)
            VALUES 
            ('2012-09-12', 'Money Mart', 750.00, '1135', 'Prepaid Visa Cards',
             'Cash', 'Prepaid Visa load $750', 'Banking')
            RETURNING receipt_id
        """)
        id2 = cur.fetchone()[0]
        print(f"  Created {id2}: $750")
    
    conn.commit()
    
    # Verify
    cur.execute("""
        SELECT COUNT(*), COALESCE(SUM(gross_amount), 0)
        FROM receipts 
        WHERE vendor_name ILIKE '%money%mart%' AND receipt_date='2012-09-12'
    """)
    cnt, total = cur.fetchone()
    print(f"\nFINAL: {cnt} transactions, Total: ${total}")
    
    conn.close()
    print("SUCCESS")
    
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
