import psycopg2
conn = psycopg2.connect(host='localhost', user='postgres', password='Arrow Limousine', dbname='almsdata')
cur = conn.cursor()

# Find Money Mart in Sept 2012
cur.execute("""SELECT receipt_id, receipt_date, gross_amount, gl_account_code 
FROM receipts WHERE vendor_name ILIKE '%money%mart%' 
AND receipt_date BETWEEN '2012-09-01' AND '2012-09-30'""")

results = cur.fetchall()
if results:
    for r in results:
        print(f"ID: {r[0]}, Date: {r[1]}, Amount: ${r[2]}, GL: {r[3]}")
else:
    print("No Money Mart transactions found in Sept 2012")

# Check GL 1135
cur.execute("SELECT account_code, account_name FROM chart_of_accounts WHERE account_code='1135'")
gl = cur.fetchone()
print(f"\nGL 1135: {gl[1] if gl else 'DOES NOT EXIST'}")

conn.close()
