import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', password='ArrowLimousine', dbname='almsdata')
cur = conn.cursor()

# Check GL 1135
cur.execute("SELECT account_code, account_name, is_active FROM chart_of_accounts WHERE account_code='1135'")
gl = cur.fetchone()

if gl:
    print(f"GL 1135: {gl[1]} (Active: {gl[2]})")
else:
    print("GL 1135: NOT FOUND")

# Check Money Mart transactions
cur.execute("""
    SELECT receipt_id, gross_amount, gl_account_code, gl_account_name
    FROM receipts 
    WHERE vendor_name ILIKE '%money%mart%' 
    AND receipt_date='2012-09-12'
    ORDER BY gross_amount DESC
""")

transactions = cur.fetchall()

if transactions:
    print(f"\nMoney Mart transactions on 09/12/2012: {len(transactions)}")
    total = 0
    for rec_id, amount, gl_code, gl_name in transactions:
        print(f"  Receipt {rec_id}: ${amount:,.2f} -> GL {gl_code} ({gl_name})")
        total += amount
    print(f"\nTotal loaded: ${total:,.2f}")
else:
    print("\nNo Money Mart transactions found on 09/12/2012")

conn.close()
